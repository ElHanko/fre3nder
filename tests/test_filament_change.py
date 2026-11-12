#!/usr/bin/env python3
"""Run reference macros through pinned Klipper; mock only hardware and time.

No simulator, chelper compilation, firmware build, or printer access is used.
KLIPPER_SOURCE can select another checkout of the pinned source revision.
"""

import configparser
from contextlib import nullcontext
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get(
    "KLIPPER_SOURCE", ROOT / "local/production/work/x2000/klipper"))
PIN = json.loads((ROOT / "configs/x2000/sources.json").read_text())["userspace"]["klipper"]["commit"]
if subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip() != PIN:
    raise SystemExit("Filament tests require the pinned Klipper checkout")
sys.dont_write_bytecode = True
sys.path.insert(0, str(SOURCE / "klippy"))
sys.path.insert(0, str(ROOT / "configs/klipper-f005"))

import gcode
from configfile import ConfigWrapper
from extras import delayed_gcode, filament_switch_sensor, gcode_macro, gcode_move
from extras import bed_mesh, homing, idle_timeout, pause_resume, safe_z_home, virtual_sdcard
import fre3nder_filament_recovery


class Status:
    def __init__(self, **values):
        self.values = values

    def get_status(self, eventtime):
        return self.values


class Clock:
    NOW = 0.0
    NEVER = 1e30

    def __init__(self):
        self.time = 10.0
        self.callbacks = []
        self.lock = Mock(__enter__=Mock(), __exit__=Mock(return_value=False))
        self.lock.test.return_value = False

    def monotonic(self):
        return self.time

    def mutex(self):
        return self.lock

    def assert_no_pause(self):
        return nullcontext()

    def pause(self, waketime):
        self.time = max(self.time, waketime)

    def register_timer(self, callback, waketime=NEVER):
        return SimpleNamespace(callback=callback, waketime=waketime)

    def update_timer(self, timer, waketime):
        timer.waketime = waketime

    def unregister_timer(self, timer):
        pass

    def register_callback(self, callback):
        self.callbacks.append(callback)


class Toolhead(Status):
    def __init__(self, printer):
        super().__init__(homed_axes="xyz", axis_minimum=gcode.Coord((-12, -20, -5)),
                         axis_maximum=gcode.Coord((221, 223, 246)))
        self.printer = printer
        self.position = [100.0, 100.0, 40.0, 123.0]
        self.moves = []
        self.homes = []
        self.position_sets = []

    def get_position(self):
        return list(self.position)

    def get_last_move_time(self):
        return self.printer.clock.time

    def get_kinematics(self):
        return self

    def clear_homing_state(self, axes):
        self.values['homed_axes'] = ''.join(
            a for a in self.values['homed_axes'] if a not in axes)

    def set_position(self, position, homing_axes=''):
        self.position_sets.append((list(position), homing_axes))
        self.position = list(position)
        self.values['homed_axes'] = ''.join(
            a for a in 'xyz' if a in self.values['homed_axes'] or a in homing_axes)
        self.printer.send_event('toolhead:set_position')

    def manual_move(self, position, speed):
        pos = self.get_position()
        for i, value in enumerate(position):
            if value is not None:
                pos[i] = value
        self.move(pos, speed)
        self.printer.send_event('toolhead:manual_move')

    def home(self, state):
        for axis in state.get_axes():
            # Only the hardware endstop/probe result is simulated. Dispatch
            # through upstream PrinterHoming and safe_z_home remains real.
            self.homes.append(('xyz'[axis], self.get_position(),
                               self.printer.objects['bed_mesh'].z_mesh,
                               self.printer.objects['heater_bed'].values['temperature'],
                               self.values['homed_axes']))
            pos = self.get_position()
            pos[axis] = (-12., -20., 2.180)[axis]
            self.set_position(pos, homing_axes='xyz'[axis])

    def move(self, position, speed):
        for i in range(3):
            if position[i] != self.position[i] and 'xyz'[i] not in self.values['homed_axes']:
                raise gcode.CommandError("Must home axis first")
            if not self.values["axis_minimum"][i] <= position[i] <= self.values["axis_maximum"][i]:
                raise gcode.CommandError("Move out of range")
        if position[3] != self.position[3] and not self.printer.objects["extruder"].values["can_extrude"]:
            raise gcode.CommandError("Extrude below minimum temp")
        self.position = list(position)
        self.moves.append((list(position), speed))
        idle = self.printer.objects.get("idle_timeout")
        if idle is not None and idle.timeout_timer is not None:
            now = self.printer.clock.time
            idle.handle_sync_print_time(now, now, now)


class Printer:
    """Small hardware boundary around upstream parsing, macros and lifecycle."""

    command_error = gcode.CommandError
    config_error = configparser.Error

    def __init__(self, recovery_xy=None, automatic_recovery=None):
        self.clock = Clock()
        self.events = {}
        self.objects = {}
        self.commands = []
        self.parser = configparser.RawConfigParser(inline_comment_prefixes=("#", ";"))
        self.parser.read(ROOT / "configs/klipper-f005/printer-f005-mainline.cfg")
        if recovery_xy is not None:
            self.parser.set('fre3nder_filament_recovery', 'home_xy_position',
                            ','.join(str(v) for v in recovery_xy))
        if automatic_recovery is not None:
            self.parser.set('fre3nder_filament_recovery', 'automatic_recovery',
                            str(automatic_recovery))
        self.access = {}
        self.objects["webhooks"] = Mock()
        self.objects["print_stats"] = Mock()
        self.objects["aio_executor"] = Mock()
        self.objects["extruder"] = Status(target=210.0, temperature=210.0, can_extrude=True)
        self.objects["heater_bed"] = Status(target=60.0, temperature=60.0)
        self.objects["probe"] = SimpleNamespace(get_offsets=lambda: (0., 27., 2.180))
        self.objects["stepper_enable"] = SimpleNamespace(motor_off=self.disable_motors)
        self.objects["configfile"] = Status(settings={
            "extruder": dict(min_extrude_temp=170.0, max_temp=320.0,
                             max_extrude_only_distance=1000.0),
            "pause_resume": dict(recover_velocity=50.0),
        })
        self.toolhead = self.objects["toolhead"] = Toolhead(self)
        self.gcode = self.objects["gcode"] = gcode.GCodeDispatch(self)
        self.objects["gcode_macro"] = gcode_macro.PrinterGCodeMacro(self.config("pause_resume"))
        self.objects["gcode_move"] = gcode_move.GCodeMove(self.config("pause_resume"))
        self.objects["homing"] = homing.PrinterHoming(self.config("safe_z_home"))
        self.objects["safe_z_home"] = safe_z_home.SafeZHoming(self.config("safe_z_home"))
        # Reuse upstream interpolation and the complete mesh transform. Only
        # calibration/MCU setup is omitted at this hardware boundary.
        mesh = self.objects['bed_mesh'] = bed_mesh.BedMesh.__new__(bed_mesh.BedMesh)
        mesh.printer, mesh.gcode, mesh.toolhead = self, self.gcode, self.toolhead
        mesh.fade_start, mesh.fade_end, mesh.fade_dist = 1., 10., 9.
        mesh.base_fade_target = mesh.fade_target = mesh.tool_offset = 0.
        mesh.z_mesh = None
        mesh.last_position = self.toolhead.get_position()
        mesh.log_fade_complete = False
        mesh.splitter = bed_mesh.MoveSplitter(self.config('bed_mesh'), self.gcode)
        mesh.pmgr = SimpleNamespace(get_profiles=lambda: {})
        self.set_mesh()
        self.objects['gcode_move'].set_move_transform(mesh)
        self.objects["pause_resume"] = pause_resume.PauseResume(self.config("pause_resume"))
        self.objects["virtual_sdcard"] = virtual_sdcard.VirtualSD(self.config("virtual_sdcard"))
        self.objects["idle_timeout"] = idle_timeout.IdleTimeout(self.config("idle_timeout"))
        self.sensor = filament_switch_sensor.RunoutHelper(
            self.config("filament_switch_sensor filament_sensor"))
        self.objects["filament_switch_sensor filament_sensor"] = self.sensor
        self.objects["delayed_gcode _FILAMENT_POWER_OFF"] = delayed_gcode.DelayedGcode(
            self.config("delayed_gcode _FILAMENT_POWER_OFF"))
        self.objects['fre3nder_filament_recovery'] = fre3nder_filament_recovery.FilamentRecovery(
            self.config('fre3nder_filament_recovery'))
        for section in self.parser.sections():
            if section.startswith("gcode_macro "):
                self.objects[section] = gcode_macro.GCodeMacro(self.config(section))
        for name in ("M104", "M109", "M140", "M190", "TURN_OFF_HEATERS", "M84", "M400", "FAIL"):
            self.gcode.register_command(name, self.hardware_command)
        self.send_event("klippy:connect")
        self.send_event("klippy:ready")
        self.clock.time += 5  # Past upstream filament-sensor startup suppression.
        self.sensor.filament_present = True
        self.move = self.objects["gcode_move"]
        self.pause = self.objects["pause_resume"]
        self.sd = self.objects["virtual_sdcard"]
        self.idle = self.objects["idle_timeout"]
        self.power = self.objects["delayed_gcode _FILAMENT_POWER_OFF"]
        self.recovery = self.objects['fre3nder_filament_recovery']

    def set_mesh(self, height=lambda x, y: 0.):
        params = dict(min_x=5., max_x=215., min_y=10., max_y=215., x_count=5,
                      y_count=5, mesh_x_pps=2, mesh_y_pps=2, algo='lagrange', tension=.2)
        mesh = bed_mesh.ZMesh(params, 'original-print')
        mesh.build_mesh([[height(5 + 52.5*x, 10 + 51.25*y) for x in range(5)]
                         for y in range(5)])
        self.objects['bed_mesh'].set_mesh(mesh)

    def disable_motors(self):
        self.toolhead.values['homed_axes'] = ''
        self.send_event('stepper_enable:motor_off')

    def config(self, section):
        return ConfigWrapper(self, self.parser, self.access, section)

    def get_start_args(self):
        return {}

    def get_reactor(self):
        return self.clock

    def register_event_handler(self, event, callback):
        self.events.setdefault(event, []).append(callback)

    def send_event(self, event, *args):
        for callback in list(self.events.get(event, [])):
            callback(*args)

    def lookup_object(self, name, default=None):
        return self.objects.get(name, default)

    def load_object(self, config, name):
        return self.objects[name]

    def invoke_shutdown(self, message):
        raise AssertionError(message)

    def is_shutdown(self):
        return False

    def run(self, commands):
        self.gcode.run_script_from_command(commands)

    def hardware_command(self, cmd):
        name = cmd.get_command()
        self.commands.append((name, self.toolhead.get_position()))
        if name in ("M104", "M109"):
            extruder = self.objects["extruder"].values
            extruder["target"] = cmd.get_float("S")
            if name == "M109":
                # Model a completed heater wait; subsequent templates see heat.
                extruder["temperature"] = extruder["target"]
                extruder["can_extrude"] = extruder["temperature"] >= 170
        elif name in ('M140', 'M190'):
            bed = self.objects['heater_bed'].values
            bed['target'] = cmd.get_float('S')
            if name == 'M190':
                bed['temperature'] = bed['target']
        elif name == "TURN_OFF_HEATERS":
            self.objects["extruder"].values["target"] = 0.0
            self.objects["heater_bed"].values["target"] = 0.0
        elif name == "M84":
            self.disable_motors()
        elif name == "FAIL":
            raise gcode.CommandError("Original print failure")


class FilamentChangeTests(unittest.TestCase):
    def setUp(self):
        self.p = Printer()
        self.p.run("G90\nM82\nG92 E17\nM220 S80\nM221 S93\nG1 F2400")
        self.initial = copy.deepcopy(self.p.move.get_status())

    def assert_modes_and_e(self, original=None):
        original = original or self.initial
        actual = self.p.move.get_status()
        for field in ("absolute_coordinates", "absolute_extrude", "speed_factor", "speed", "extrude_factor"):
            self.assertEqual(actual[field], original[field], field)
        self.assertAlmostEqual(actual["gcode_position"].e, original["gcode_position"].e)

    def power_off(self):
        self.p.run('PAUSE')
        timer = self.p.power.timer_handler
        self.p.clock.time = timer.waketime
        timer.waketime = self.p.power._gcode_timer_event(self.p.clock.time)
        self.p.objects['extruder'].values.update(temperature=25., can_extrude=False)
        self.p.objects['heater_bed'].values['temperature'] = 25.

    def test_manual_pause_parks_after_lift_and_is_idempotent(self):
        self.p.run("PAUSE")
        self.assertTrue(self.p.pause.is_paused)
        self.assertEqual(self.p.toolhead.position[:3], [-2.0, 20.0, 90.0])
        self.assertEqual(self.p.toolhead.moves[-2][0][:3], [100.0, 100.0, 90.0])
        self.assertEqual(self.p.toolhead.position[3], 122.0)
        saved = copy.deepcopy(self.p.move.saved_states["PAUSE_STATE"])
        deadline = self.p.power.timer_handler.waketime
        self.p.run("PAUSE")
        self.assertEqual(self.p.move.saved_states["PAUSE_STATE"], saved)
        self.assertEqual(self.p.power.timer_handler.waketime, deadline)
        self.assertEqual(self.p.idle.idle_timeout, 300)
        self.assert_modes_and_e()

    def test_runout_uses_the_same_pause_without_automatic_resume(self):
        self.p.idle.state = "Printing"
        self.p.sensor.note_filament_present(self.p.clock.time, False)
        self.assertEqual(len(self.p.clock.callbacks), 1)
        self.p.clock.callbacks.pop()(self.p.clock.time)
        self.assertTrue(self.p.pause.is_paused)
        self.assertEqual(self.p.toolhead.position[:3], [-2.0, 20.0, 90.0])
        with self.assertLogs(level="ERROR"), self.assertRaisesRegex(gcode.CommandError, "Insert filament"):
            self.p.run("RESUME")
        self.p.sensor.note_filament_present(self.p.clock.time + 5, True)
        self.assertTrue(self.p.pause.is_paused)

    def test_load_unload_and_repeated_purge_preserve_the_pause_state(self):
        self.p.run("PAUSE")
        saved = copy.deepcopy(self.p.move.saved_states["PAUSE_STATE"])
        self.p.objects["extruder"].values.update(target=0, temperature=25, can_extrude=False)
        before = self.p.toolhead.position[3]
        self.p.run("LOAD LENGTH=45\nUNLOAD LENGTH=55\nPURGE LENGTH=20\nPURGE LENGTH=12")
        self.assertAlmostEqual(self.p.toolhead.position[3] - before, 45 - 55 + 20 + 12)
        self.assertEqual(self.p.objects["extruder"].values["target"], 210)
        self.assertEqual(self.p.toolhead.position[:3], [-1.7, 30.0, 90.0])
        self.assertTrue(self.p.pause.is_paused)
        self.assertEqual(self.p.move.saved_states["PAUSE_STATE"], saved)
        self.assert_modes_and_e()

    def test_resume_reheats_and_returns_xy_before_lowering_z(self):
        self.p.idle.idle_timeout = 900
        self.p.run("PAUSE\nPURGE")
        self.p.run('M104 S0')  # A heater adjustment without releasing motors.
        self.assertEqual(self.p.objects["extruder"].values["target"], 0)
        self.assertEqual(self.p.objects["heater_bed"].values["target"], 60)
        self.assertEqual(self.p.toolhead.values["homed_axes"], "xyz")
        self.p.objects["extruder"].values.update(temperature=25, can_extrude=False)
        self.p.toolhead.moves.clear()
        self.p.run("RESUME VELOCITY=35")
        self.assertEqual(self.p.objects["extruder"].values["target"], 210)
        self.assertEqual(self.p.toolhead.moves[-2][0][:3], [100.0, 100.0, 90.0])
        self.assertEqual(self.p.toolhead.moves[-1][0][:3], [100.0, 100.0, 40.0])
        self.assertEqual(self.p.toolhead.moves[-1][1], 35)
        self.assertFalse(self.p.pause.is_paused)
        self.assertEqual(self.p.idle.idle_timeout, 900)
        self.assertEqual(self.p.power.timer_handler.waketime, self.p.clock.NEVER)
        self.assert_modes_and_e()

    def test_offsets_and_relative_modes_do_not_shift_the_purge_area(self):
        self.p.run("G92 X7 Y8 Z9\nG91\nM83")
        original = copy.deepcopy(self.p.move.get_status())
        self.p.run("PAUSE\nLOAD\nUNLOAD\nPURGE\nRESUME")
        self.assertEqual(self.p.toolhead.position[:3], [100.0, 100.0, 40.0])
        self.assertIn([-1.7, 145.0, 90.0],
                      [[round(v, 6) for v in pos[:3]] for pos, speed in self.p.toolhead.moves])
        self.assert_modes_and_e(original)

    def test_virtual_sd_print_stays_paused_and_continues_at_the_next_line(self):
        self.p.sd.current_file = io.StringIO(
            "G1 X110 Y90 Z41 E18 F1200\nPAUSE\nG1 X120 Y80 Z42 E19\n")
        self.p.sd.work_timer = object()
        self.p.sd.work_handler(self.p.clock.time)
        self.assertTrue(self.p.pause.is_paused)
        self.assertTrue(self.p.pause.sd_paused)
        self.assertIsNone(self.p.sd.work_timer)
        self.assertEqual(self.p.toolhead.position[:3], [-2.0, 20.0, 91.0])
        file_position = self.p.sd.file_position
        self.p.run("LOAD\nUNLOAD\nPURGE\nPURGE")
        self.assertEqual(self.p.sd.file_position, file_position)
        self.assertIsNone(self.p.sd.work_timer)
        self.p.run("RESUME")
        extrusion_before = self.p.toolhead.position[3]
        self.assertIsNotNone(self.p.sd.work_timer)
        self.p.sd.work_handler(self.p.clock.time)
        self.assertEqual(self.p.toolhead.position[:3], [120.0, 80.0, 42.0])
        self.assertAlmostEqual(self.p.toolhead.position[3] - extrusion_before, .93)
        self.assertAlmostEqual(self.p.move.get_status()["gcode_position"].e, 19)
        self.p.objects["print_stats"].note_complete.assert_called_once()

    def test_z_limit_and_lost_homing_leave_the_print_paused(self):
        self.p.run("G1 Z244\nPAUSE\nPURGE")
        self.assertEqual(self.p.toolhead.position[2], 246)
        self.p.toolhead.values["homed_axes"] = "xy"
        moves = len(self.p.toolhead.moves)
        with self.assertLogs(level="WARNING"), self.assertRaisesRegex(gcode.CommandError, "automatic recovery is disabled"):
            self.p.run("RESUME")
        self.assertEqual(len(self.p.toolhead.moves), moves)
        self.assertTrue(self.p.pause.is_paused)
        self.p = Printer()
        self.p.sd.current_file = io.StringIO("G1 Z245\nPAUSE\nG1 X110\n")
        self.p.sd.work_timer = object()
        self.p.sd.work_handler(self.p.clock.time)
        self.assertTrue(self.p.pause.is_paused)
        self.assertIsNotNone(self.p.sd.current_file)
        self.assertIsNone(self.p.sd.work_timer)
        self.assertEqual(self.p.toolhead.position[:3], [100.0, 100.0, 245.0])
        with self.assertLogs(level="ERROR"), self.assertRaisesRegex(gcode.CommandError, "Insufficient Z"):
            self.p.run("PURGE")
        self.assertTrue(self.p.pause.is_paused)
        self.assertEqual(self.p.toolhead.position[:3], [100.0, 100.0, 245.0])

    def test_commands_reject_unsafe_use_before_motion(self):
        for command in ("LOAD", "UNLOAD", "PURGE", "RESUME", "RECOVER_HOMING"):
            with self.subTest(command=command), self.assertLogs(level="WARNING"), self.assertRaises(gcode.CommandError):
                self.p.run(command)
        self.p.run("PAUSE")
        for command in ("LOAD LENGTH=-1", "UNLOAD LENGTH=1001", "PURGE LENGTH=0",
                        "LOAD TEMPERATURE=100", "PURGE TEMPERATURE=400", "RESUME VELOCITY=0",
                        "RECOVER_HOMING"):
            moves = len(self.p.toolhead.moves)
            with self.subTest(command=command), self.assertLogs(level="WARNING"), self.assertRaises(gcode.CommandError):
                self.p.run(command)
            self.assertEqual(len(self.p.toolhead.moves), moves)

    def test_cold_manual_pause_requires_an_explicit_filament_temperature(self):
        self.p.objects["extruder"].values.update(target=0, temperature=25, can_extrude=False)
        before = self.p.toolhead.position[3]
        self.p.run("PAUSE")
        self.assertEqual(self.p.toolhead.position[3], before)
        with self.assertLogs(level="ERROR"), self.assertRaises(gcode.CommandError):
            self.p.run("LOAD")
        self.p.run("LOAD LENGTH=10 TEMPERATURE=210")
        self.assertEqual(self.p.toolhead.position[3] - before, 10)
        self.assertTrue(self.p.pause.is_paused)

    def test_poweroff_after_300_seconds_retains_the_job_without_an_expiry(self):
        self.p.sd.current_file = io.StringIO("PAUSE\nG1 X110\n")
        self.p.sd.work_timer = object()
        self.p.sd.work_handler(self.p.clock.time)
        saved = copy.deepcopy(self.p.move.saved_states['PAUSE_STATE'])
        mesh = copy.deepcopy(self.p.objects['bed_mesh'].z_mesh.mesh_matrix)
        position = self.p.toolhead.get_position()
        file_position = self.p.sd.file_position
        deadline = self.p.power.timer_handler.waketime
        self.p.clock.time = deadline - 1
        self.p.run("LOAD\nPURGE\nPAUSE")
        self.assertEqual(self.p.power.timer_handler.waketime, deadline)
        self.assertEqual(self.p.objects['heater_bed'].values['target'], 60)
        self.assertEqual(self.p.toolhead.values['homed_axes'], 'xyz')
        position = self.p.toolhead.get_position()
        self.p.clock.time = deadline
        self.p.power.timer_handler.waketime = self.p.power._gcode_timer_event(deadline)
        self.assertIsNotNone(self.p.sd.current_file)
        self.assertTrue(self.p.pause.is_paused)
        self.assertEqual(self.p.toolhead.values["homed_axes"], "")
        self.assertEqual(self.p.objects["heater_bed"].values["target"], 0)
        self.assertEqual(self.p.objects["extruder"].values["target"], 0)
        self.assertEqual(self.p.toolhead.get_position(), position)
        self.assertEqual(self.p.recovery.snapshot['bed'], 60)
        self.assertEqual(self.p.recovery.snapshot['hotend'], 210)
        self.p.clock.time += 1e7
        self.p.idle.transition_idle_state(self.p.clock.time)
        self.assertTrue(self.p.pause.is_paused)
        self.assertEqual(self.p.sd.file_position, file_position)
        self.assertEqual(self.p.move.saved_states['PAUSE_STATE'], saved)
        self.assertEqual(self.p.objects['bed_mesh'].z_mesh.mesh_matrix, mesh)
        self.p.objects['print_stats'].note_cancel.assert_not_called()
        self.assertEqual(self.p.power.timer_handler.waketime, self.p.clock.NEVER)

    def test_explicit_cancel_restores_normal_idle_shutdown(self):
        self.p.run('PAUSE\nCANCEL_PRINT')
        self.assertFalse(self.p.pause.is_paused)
        self.assertEqual(self.p.idle.idle_timeout, 600)
        self.assertEqual(self.p.power.timer_handler.waketime, self.p.clock.NEVER)
        self.assertIsNone(self.p.recovery.snapshot)
        self.assertEqual(self.p.toolhead.values['homed_axes'], '')
        self.assertEqual(self.p.objects['heater_bed'].values['target'], 0)

    def test_clear_pause_cannot_discard_a_waiting_print(self):
        self.p.run('PAUSE')
        for cooled in (False, True):
            if cooled:
                self.p.run('_FILAMENT_POWER_OFF')
            with self.assertLogs(level='ERROR'), self.assertRaisesRegex(gcode.CommandError, 'CANCEL_PRINT'):
                self.p.run('CLEAR_PAUSE')
            self.assertTrue(self.p.pause.is_paused)
            self.assertIsNotNone(self.p.recovery.snapshot)
        self.p.run('CANCEL_PRINT\nCLEAR_PAUSE')
        self.assertFalse(self.p.pause.is_paused)

    def test_recovery_homes_at_rear_edge_and_restores_the_original_mesh_frame(self):
        height = lambda x, y: .1 + .001*x - .0003*y
        self.p.set_mesh(height)
        self.p.objects['bed_mesh'].tool_offset = .5
        self.p.run('G92 X7 Y8 Z9\nG91\nM83')
        original = copy.deepcopy(self.p.move.get_status())
        self.power_off()
        saved = copy.deepcopy(self.p.move.saved_states['PAUSE_STATE'])
        matrix = copy.deepcopy(self.p.objects['bed_mesh'].z_mesh.mesh_matrix)
        self.p.run('RECOVER_HOMING')
        self.assertEqual([h[0] for h in self.p.toolhead.homes], ['x', 'y', 'z', 'z'])
        self.assertEqual([h[4] for h in self.p.toolhead.homes], ['', 'x', 'xy', 'xyz'])
        for home in self.p.toolhead.homes:
            self.assertIsNone(home[2], 'Mesh compensation must be disabled during raw homing')
        z_homes = [h for h in self.p.toolhead.homes if h[0] == 'z']
        self.assertEqual([h[1][:2] for h in z_homes], [[10., 178.], [10., 178.]])
        self.assertEqual([h[3] for h in z_homes], [25., 60.])
        # Rear BLTouch is at (10,205), inside the measured mesh. This software
        # test does not qualify the physical point, part clearance or bed sweep.
        self.assertAlmostEqual(self.p.recovery.correction, height(10., 205.))
        self.assertNotAlmostEqual(self.p.recovery.correction, height(10., 205.) - height(110., 110.))
        corrected = [pos for pos, axes in self.p.toolhead.position_sets
                     if abs(pos[2] - (2.180 + height(10., 205.))) < 1e-9]
        self.assertTrue(corrected, 'Calibrated probe offset must be included exactly once')
        self.assertEqual(self.p.objects['bed_mesh'].z_mesh.mesh_matrix, matrix)
        self.assertEqual(self.p.objects['bed_mesh'].tool_offset, .5)
        self.assertEqual(self.p.move.saved_states['PAUSE_STATE'], saved)
        self.assertEqual(self.p.toolhead.position[:3], [10., 178., 90.])
        self.assertTrue(self.p.pause.is_paused)
        self.assertTrue(self.p.recovery.ready)
        self.assert_modes_and_e(original)

    def test_recovery_resume_returns_to_the_unchanged_sd_print(self):
        self.p.recovery.automatic_recovery = True  # Model a qualified installation.
        self.p.sd.current_file = io.StringIO('PAUSE\nG1 X120 Y80 Z42 E18\n')
        self.p.sd.work_timer = object()
        self.p.sd.work_handler(self.p.clock.time)
        position = self.p.sd.file_position
        self.power_off()
        for command in ('LOAD', 'UNLOAD', 'PURGE'):
            with self.subTest(command=command), self.assertLogs(level='WARNING'), self.assertRaises(gcode.CommandError):
                self.p.run(command)
        saved = copy.deepcopy(self.p.move.saved_states['PAUSE_STATE'])
        output = []
        self.p.gcode.register_output_handler(output.append)
        self.p.run('RESUME')
        self.assertTrue(self.p.pause.is_paused)
        self.assertIsNone(self.p.sd.work_timer)
        self.assertEqual(self.p.toolhead.position[:3], [10., 178., 90.])
        self.assertEqual(self.p.move.saved_states['PAUSE_STATE'], saved)
        self.assertTrue(any('press RESUME again' in line for line in output))
        self.assertEqual(self.p.sd.file_position, position)
        self.p.run('LOAD LENGTH=10\nPURGE LENGTH=5')
        self.assertTrue(self.p.pause.is_paused)
        homes = len(self.p.toolhead.homes)
        self.p.run('RESUME VELOCITY=35')
        self.assertFalse(self.p.pause.is_paused)
        self.assertEqual(self.p.toolhead.position[:3], [100., 100., 40.])
        self.assertEqual(self.p.toolhead.moves[-1][1], 35.)
        self.assertEqual(len(self.p.toolhead.homes), homes)
        self.assertEqual(self.p.idle.idle_timeout, 600)
        before = self.p.toolhead.position[3]
        self.p.sd.work_handler(self.p.clock.time)
        self.assertEqual(self.p.toolhead.position[:3], [120., 80., 42.])
        self.assertAlmostEqual(self.p.toolhead.position[3] - before, .93)
        self.assert_modes_and_e(dict(self.initial, gcode_position=gcode.Coord((120, 80, 42, 18))))
        moves = len(self.p.toolhead.moves)
        for _ in range(2):
            with self.assertLogs(level='ERROR'), self.assertRaisesRegex(gcode.CommandError, 'No filament pause'):
                self.p.run('RESUME')
        self.assertEqual(len(self.p.toolhead.moves), moves)

    def test_default_resume_does_not_home_an_unqualified_recovery_point(self):
        self.assertFalse(self.p.recovery.automatic_recovery)
        self.power_off()
        saved = copy.deepcopy(self.p.move.saved_states['PAUSE_STATE'])
        moves = len(self.p.toolhead.moves)
        for _ in range(2):
            with self.assertLogs(level='WARNING'), self.assertRaisesRegex(gcode.CommandError, 'hardware validated'):
                self.p.run('RESUME')
        self.assertFalse(self.p.toolhead.homes)
        self.assertEqual(len(self.p.toolhead.moves), moves)
        self.assertTrue(self.p.pause.is_paused)
        self.assertEqual(self.p.move.saved_states['PAUSE_STATE'], saved)
        # A separate, deliberate diagnostic command remains available.
        self.p.run('RECOVER_HOMING')
        self.assertTrue(self.p.recovery.ready)
        self.assertTrue(self.p.pause.is_paused)

    def test_recovery_resume_reapplies_fading_mesh_compensation_exactly_once(self):
        self.p.set_mesh(lambda x, y: .1 + .001*x - .0003*y)
        self.p.run('G1 Z4')
        physical = self.p.toolhead.get_position()
        original = copy.deepcopy(self.p.move.get_status())
        self.assertNotAlmostEqual(physical[2], 4., msg='Test must exercise active mesh fade')
        self.power_off()
        self.p.run('RECOVER_HOMING')
        self.p.run('RESUME')
        for expected, actual in zip(physical[:3], self.p.toolhead.position[:3]):
            self.assertAlmostEqual(actual, expected)
        self.assertAlmostEqual(self.p.move.get_status()['gcode_position'].z,
                               original['gcode_position'].z)
        self.assert_modes_and_e(original)

    def test_recovery_rejects_out_of_bounds_or_nonfinite_geometry_before_motion(self):
        for point in ((300, 178), (1, 178), (10, 224), (10, 189),
                      (10, -19), (float('nan'), 178)):
            with self.subTest(point=point):
                self.p = Printer(recovery_xy=point)
                self.power_off()
                moves = len(self.p.toolhead.moves)
                with self.assertLogs(level='WARNING'), self.assertRaisesRegex(gcode.CommandError, 'geometry'):
                    self.p.run('RECOVER_HOMING')
                self.assertFalse(self.p.toolhead.homes)
                self.assertEqual(len(self.p.toolhead.moves), moves)
                self.assertTrue(self.p.pause.is_paused)

    def test_recovery_point_can_be_configured_to_the_former_front_point(self):
        self.p = Printer(recovery_xy=(10, -12))
        self.power_off()
        self.p.run('RECOVER_HOMING')
        z_homes = [h for h in self.p.toolhead.homes if h[0] == 'z']
        self.assertEqual([h[1][:2] for h in z_homes], [[10., -12.], [10., -12.]])

    def test_recovery_accepts_a_raised_park_below_the_former_50mm_requirement(self):
        for print_z in (220, 244):
            with self.subTest(print_z=print_z):
                self.p = Printer()
                self.p.run('G1 Z%d' % print_z)
                self.power_off()
                self.assertEqual(self.p.recovery.get_status(0.)['commanded_lift'], 246 - print_z)
                self.p.run('RECOVER_HOMING\nRESUME')
                self.assertFalse(self.p.pause.is_paused)
                self.assertEqual(self.p.toolhead.position[:3], [100., 100., print_z])

    def test_recovery_refuses_when_pause_could_not_establish_a_raised_park(self):
        self.p.run('G1 Z245')
        self.power_off()
        with self.assertLogs(level='WARNING'), self.assertRaisesRegex(gcode.CommandError, 'raised park'):
            self.p.run('RECOVER_HOMING')
        self.assertFalse(self.p.toolhead.homes)

    def test_recovery_stops_when_mesh_or_reference_is_unavailable(self):
        for mode in ('missing', 'zero_reference', 'changed'):
            with self.subTest(mode=mode):
                self.p = Printer()
                if mode == 'missing':
                    self.p.objects['bed_mesh'].set_mesh(None)
                elif mode == 'zero_reference':
                    self.p.recovery.zero_reference = '110,110'
                self.power_off()
                if mode == 'changed':
                    self.p.objects['bed_mesh'].z_mesh.mesh_offsets[0] = 1.
                with self.assertLogs(level='WARNING'), self.assertRaises(gcode.CommandError):
                    self.p.run('RECOVER_HOMING')
                self.assertFalse(self.p.toolhead.homes)
                self.assertTrue(self.p.pause.is_paused)

    def test_recovery_stops_when_captured_state_or_mesh_frame_changes(self):
        for mode in ('file', 'cursor', 'pause_state', 'probe_offset', 'fade', 'sd_command'):
            with self.subTest(mode=mode):
                self.p = Printer()
                self.power_off()
                if mode == 'file':
                    self.p.sd.current_file = io.StringIO('G1 X1\n')
                elif mode == 'cursor':
                    self.p.sd.file_position += 1
                elif mode == 'pause_state':
                    self.p.move.saved_states['PAUSE_STATE']['last_position'][0] += 1
                elif mode == 'probe_offset':
                    self.p.objects['probe'].get_offsets = lambda: (0., 28., 2.180)
                elif mode == 'fade':
                    self.p.objects['bed_mesh'].tool_offset += .5
                else:
                    self.p.sd.cmd_from_sd = True
                moves = len(self.p.toolhead.moves)
                with self.assertLogs(level='WARNING'), self.assertRaises(gcode.CommandError):
                    self.p.run('RECOVER_HOMING')
                self.assertFalse(self.p.toolhead.homes)
                self.assertEqual(len(self.p.toolhead.moves), moves)
                self.assertTrue(self.p.pause.is_paused)

    def test_recovery_resume_requires_stable_temperatures_mesh_and_filament(self):
        for mode in ('hotend', 'bed', 'target', 'filament', 'mesh'):
            with self.subTest(mode=mode):
                self.p = Printer()
                self.power_off()
                self.p.run('RECOVER_HOMING')
                if mode == 'hotend':
                    self.p.objects['extruder'].values['temperature'] -= 5
                elif mode == 'bed':
                    self.p.objects['heater_bed'].values['temperature'] -= 5
                elif mode == 'target':
                    self.p.objects['extruder'].values['target'] = 0
                elif mode == 'filament':
                    self.p.sensor.filament_present = False
                else:
                    self.p.objects['bed_mesh'].set_mesh(None)
                moves = len(self.p.toolhead.moves)
                with self.assertLogs(level='WARNING'), self.assertRaises(gcode.CommandError):
                    self.p.run('RESUME')
                self.assertEqual(len(self.p.toolhead.moves), moves)
                self.assertTrue(self.p.pause.is_paused)

    def test_homing_failure_keeps_the_snapshot_and_shuts_down(self):
        self.p = Printer(automatic_recovery=True)
        self.power_off()
        saved = copy.deepcopy(self.p.move.saved_states['PAUSE_STATE'])
        normal_home = self.p.toolhead.home
        def fail_y(state):
            if state.get_axes() == [1]:
                raise gcode.CommandError('Y endstop test failure')
            normal_home(state)
        self.p.toolhead.home = fail_y
        with self.assertLogs(level='WARNING'), self.assertRaisesRegex(gcode.CommandError, 'Y endstop test failure'):
            self.p.run('RESUME')
        self.assertEqual(self.p.toolhead.values['homed_axes'], '')
        self.assertEqual(self.p.objects['heater_bed'].values['target'], 0.)
        self.assertIsNotNone(self.p.objects['bed_mesh'].z_mesh)
        self.assertEqual(self.p.move.saved_states['PAUSE_STATE'], saved)
        self.assertTrue(self.p.pause.is_paused)
        self.assertFalse(self.p.recovery.ready)
        self.assertTrue(self.p.recovery.homing_failed)
        moves, homes = len(self.p.toolhead.moves), len(self.p.toolhead.homes)
        for _ in range(2):
            with self.assertLogs(level='WARNING'), self.assertRaisesRegex(gcode.CommandError, 'will not repeat'):
                self.p.run('RESUME')
        self.assertEqual(len(self.p.toolhead.moves), moves)
        self.assertEqual(len(self.p.toolhead.homes), homes)
        self.assertEqual(self.p.move.saved_states['PAUSE_STATE'], saved)
        # Only an explicit diagnostic retry clears the failed-homing latch.
        self.p.toolhead.home = normal_home
        self.p.run('RECOVER_HOMING')
        self.assertFalse(self.p.recovery.homing_failed)
        self.assertTrue(self.p.recovery.ready)
        self.assertTrue(self.p.pause.is_paused)

    def test_motor_release_after_recovery_invalidates_readiness_again(self):
        self.p = Printer(automatic_recovery=True)
        self.power_off()
        self.p.run('RESUME')
        self.p.run('_FILAMENT_POWER_OFF')
        self.assertFalse(self.p.recovery.ready)
        self.p.run('RESUME')
        self.assertTrue(self.p.recovery.ready)
        self.assertTrue(self.p.pause.is_paused)
        self.assertEqual(len(self.p.toolhead.homes), 8)
        self.p.run('RESUME')
        self.assertFalse(self.p.pause.is_paused)

    def test_reference_loss_without_motor_off_event_requires_recovery_again(self):
        self.p = Printer(automatic_recovery=True)
        self.p.sd.current_file = io.StringIO('PAUSE\nG1 X120\n')
        self.p.sd.work_timer = object()
        self.p.sd.work_handler(self.p.clock.time)
        self.assertFalse(self.p.recovery.powered_down)
        self.p.toolhead.values['homed_axes'] = 'xy'
        self.p.run('RESUME')
        self.assertTrue(self.p.recovery.ready)
        self.assertTrue(self.p.pause.is_paused)
        self.p.toolhead.values['homed_axes'] = 'xy'
        self.p.run('RESUME')
        self.assertEqual(len(self.p.toolhead.homes), 8)
        self.assertTrue(self.p.pause.is_paused)
        self.p.run('RESUME')
        self.assertFalse(self.p.pause.is_paused)

    def test_cancel_discards_ready_or_failed_recovery_state(self):
        for failed in (False, True):
            with self.subTest(failed=failed):
                self.p = Printer(automatic_recovery=True)
                self.power_off()
                if failed:
                    self.p.toolhead.home = Mock(side_effect=gcode.CommandError('Homing failed'))
                    with self.assertLogs(level='WARNING'), self.assertRaises(gcode.CommandError):
                        self.p.run('RESUME')
                else:
                    self.p.run('RESUME')
                self.p.run('CANCEL_PRINT')
                self.assertFalse(self.p.pause.is_paused)
                self.assertIsNone(self.p.recovery.snapshot)
                self.assertFalse(self.p.recovery.ready)
                self.assertFalse(self.p.recovery.homing_failed)
                self.assertEqual(self.p.objects['heater_bed'].values['target'], 0)
                self.assertEqual(self.p.objects['extruder'].values['target'], 0)
                self.assertEqual(self.p.toolhead.values['homed_axes'], '')

    def test_normal_safe_z_homing_keeps_its_original_central_point(self):
        self.p.run('G28')
        z_home = [h for h in self.p.toolhead.homes if h[0] == 'z']
        self.assertEqual(len(z_home), 1)
        self.assertEqual(z_home[0][1][:2], [110., 83.])

    def test_sd_error_preserves_original_error_without_recursive_abort_failure(self):
        self.p.sd.current_file = io.StringIO("FAIL\n")
        self.p.sd.work_timer = object()
        with self.assertNoLogs(level="ERROR"):
            self.p.sd.work_handler(self.p.clock.time)
        self.p.objects["print_stats"].note_error.assert_called_once_with("Original print failure")
        self.p.objects["print_stats"].note_cancel.assert_called_once()
        self.assertIsNone(self.p.sd.current_file)
        self.assertFalse(self.p.pause.is_paused)
        self.assertEqual(self.p.objects["extruder"].values["target"], 0)

    def test_start_purge_preserves_original_path_and_shares_custom_coordinates(self):
        profile = json.loads((ROOT / "configs/orcaslicer/Fre3nder Ender-3 V3 KE 0.4 nozzle.json").read_text())
        self.assertIn("START_PURGE TEMPERATURE=[nozzle_temperature_initial_layer]", profile["machine_start_gcode"])
        self.p.run("G90\nM83\nM220 S100\nM221 S100\nSTART_PURGE TEMPERATURE=210")
        expected = [([-2, 20, .3], 5000 / 60), ([-2, 20, .2], 5000 / 60),
                    ([-2, 145, .2], 1500 / 60), ([-1.7, 145, .2], 5000 / 60),
                    ([-1.7, 30, .2], 1500 / 60)]
        # The profile resets speed/flow before reaching its start-purge block.
        for (position, speed), (xyz, feed) in zip(self.p.toolhead.moves[-5:], expected):
            self.assertEqual(position[:3], xyz)
            self.assertAlmostEqual(speed, feed)
        self.assertEqual(self.p.move.get_status()["gcode_position"].e, 0)
        self.assertAlmostEqual(self.p.toolhead.position[3] - 123, 30)
        self.p.run("SET_GCODE_VARIABLE MACRO=_FILAMENT_SETTINGS VARIABLE=purge_x VALUE=-3.0\n"
                   "SET_GCODE_VARIABLE MACRO=_FILAMENT_SETTINGS VARIABLE=purge_y VALUE=25.0\n"
                   "START_PURGE TEMPERATURE=210")
        self.assertEqual(self.p.toolhead.moves[-5][0][:2], [-3, 25])
        self.p.run("PAUSE\nPURGE")
        self.assertIn([-3, 25], [pos[:2] for pos, speed in self.p.toolhead.moves[-5:]])


if __name__ == "__main__":
    unittest.main()
