"""Operator-requested filament recovery for the pinned Klipper API.

Normal safe_z_home is unchanged. RESUME delegates lost-reference handling here.
See docs/configuration.md before qualification on a physical printer.
"""

import copy
import math


class FilamentRecovery:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.recovery_xy = config.getfloatlist('home_xy_position', count=2)
        self.automatic_recovery = config.getboolean('automatic_recovery', False)
        self.probe_lift = config.getfloat('probe_lift', 8., above=0.)
        self.speed = config.getfloat('travel_speed', 20., above=0.)
        self.zero_reference = config.getsection('bed_mesh').get(
            'zero_reference_position', None, note_valid=False)
        self.home_xy = config.getsection('safe_z_home').getfloatlist(
            'home_xy_position', count=2)
        self.reset()
        self.printer.register_event_handler(
            'stepper_enable:motor_off', self.motor_off)
        for name, method in (
                ('FILAMENT_RECOVERY_CAPTURE', self.capture),
                ('FILAMENT_RECOVERY_PARKED', self.parked),
                ('FILAMENT_RECOVERY_POWER_OFF', self.power_off),
                ('FILAMENT_RECOVERY_RESET', self.cmd_reset),
                ('RECOVER_HOMING', self.home),
                ('_FILAMENT_RECOVERY_RESUME', self.resume)):
            self.gcode.register_command(name, method)

    def reset(self):
        self.snapshot = None
        self.powered_down = self.ready = False
        self.homing_failed = False
        self.park_position = None
        self.mesh_error = ''
        self.correction = None

    def cmd_reset(self, gcmd):
        self.reset()

    def status(self, name):
        return self.printer.lookup_object(name).get_status(
            self.printer.get_reactor().monotonic())

    def get_status(self, eventtime):
        lift = 0. if self.park_position is None or self.snapshot is None else (
            self.park_position[2] - self.snapshot['state']['last_position'][2])
        return dict(powered_down=self.powered_down, ready=self.ready,
                    homing_failed=self.homing_failed,
                    commanded_lift=lift, mesh_error=self.mesh_error,
                    z_correction=self.correction)

    def capture(self, gcmd):
        move = self.printer.lookup_object('gcode_move')
        bedmesh = self.printer.lookup_object('bed_mesh')
        mesh = bedmesh.z_mesh
        offsets = tuple(self.printer.lookup_object('probe').get_offsets())
        self.reset()
        self.snapshot = dict(
            state=copy.deepcopy(move.saved_states['PAUSE_STATE']),
            mesh=copy.deepcopy(mesh), offsets=offsets,
            hotend=self.status('extruder')['target'],
            bed=self.status('heater_bed')['target'],
            fade=(bedmesh.fade_start, bedmesh.fade_end,
                  bedmesh.base_fade_target, bedmesh.tool_offset))
        if (mesh is None or not mesh.mesh_matrix or not mesh.probed_matrix
                or mesh.mesh_params['x_count'] != 5 or mesh.mesh_params['y_count'] != 5):
            self.mesh_error = 'Recovery requires the original 5x5 mesh'
        elif self.zero_reference is not None or any(mesh.mesh_offsets):
            self.mesh_error = 'Recovery requires an unshifted mesh in the original homing frame'
        elif not all(math.isfinite(z) for row in mesh.mesh_matrix for z in row):
            self.mesh_error = 'Recovery mesh contains invalid heights'

    def parked(self, gcmd):
        if self.snapshot is None:
            return
        pos = self.status('gcode_move')['position']
        settings = self.status('gcode_macro _FILAMENT_SETTINGS')
        # This records only the commanded park, never a claim of physical Z.
        if (pos.x < 0 and abs(pos.x - settings['purge_x']) < .001
                and abs(pos.y - settings['purge_y']) < .001):
            self.park_position = tuple(pos)

    def power_off(self, gcmd):
        if self.snapshot is not None and not self.powered_down:
            sd = self.printer.lookup_object('virtual_sdcard')
            self.snapshot['file'] = sd.current_file
            self.snapshot['file_position'] = sd.file_position
        self.powered_down = True
        self.ready = False

    def motor_off(self):
        if self.snapshot is not None:
            self.power_off(None)

    def check_pause(self, gcmd):
        if self.snapshot is None or not self.status('pause_resume')['is_paused']:
            raise gcmd.error('No captured filament pause')
        sd = self.printer.lookup_object('virtual_sdcard')
        if sd.is_cmd_from_sd():
            raise gcmd.error('Recovery must be requested separately from the SD file')
        if (sd.current_file is not self.snapshot.get('file')
                or sd.file_position != self.snapshot.get('file_position')):
            raise gcmd.error('The paused SD job changed; recovery stopped')
        if self.printer.lookup_object('gcode_move').saved_states.get(
                'PAUSE_STATE') != self.snapshot['state']:
            raise gcmd.error('The saved print state changed; recovery stopped')

    def check_mesh(self, gcmd):
        if self.mesh_error:
            raise gcmd.error(self.mesh_error)
        offsets = tuple(self.printer.lookup_object('probe').get_offsets())
        if offsets != self.snapshot['offsets']:
            raise gcmd.error('Probe offsets changed during the pause')
        mesh = self.printer.lookup_object('bed_mesh').z_mesh
        saved = self.snapshot['mesh']
        if mesh is None or any(getattr(mesh, field) != getattr(saved, field)
                               for field in ('mesh_params', 'mesh_offsets',
                                             'mesh_matrix', 'probed_matrix')):
            raise gcmd.error('The original mesh is no longer active')
        bedmesh = self.printer.lookup_object('bed_mesh')
        if (bedmesh.fade_start, bedmesh.fade_end,
                bedmesh.base_fade_target, bedmesh.tool_offset) != self.snapshot['fade']:
            raise gcmd.error('Mesh compensation changed during the pause')

    def raw_home(self, axis):
        # Bypass only safe_z_home's automatic hop/centre move. The pinned
        # upstream homing module still performs real endstop/probe homing.
        cmd = self.gcode.create_gcode_command('G28', 'G28 ' + axis, {axis: '0'})
        self.printer.lookup_object('homing').cmd_G28(cmd)

    def reheat(self):
        self.gcode.run_script_from_command(
            'M190 S%s\nM109 S%s' % (
                self.snapshot['bed'], self.snapshot['hotend']))

    def home(self, gcmd):
        if not self.powered_down and self.status('toolhead')['homed_axes'] != 'xyz':
            self.power_off(None)
        self.check_pause(gcmd)
        if not self.powered_down:
            raise gcmd.error('Use normal RESUME while the original reference is valid')
        # A raised commanded park is needed for the later return. Actual
        # gantry clearance and adhesion must be inspected before recovery;
        # neither a fixed lift nor a confirmation flag can establish them.
        min_lift = self.status('gcode_macro _FILAMENT_SETTINGS')['min_lift']
        if (self.park_position is None or min_lift <= 0.
                or self.get_status(0.)['commanded_lift'] < min_lift - 1.e-6):
            raise gcmd.error('Recovery requires a recorded raised park position')
        self.check_mesh(gcmd)
        x, y = self.recovery_xy
        px, py = x + self.snapshot['offsets'][0], y + self.snapshot['offsets'][1]
        toolhead = self.printer.lookup_object('toolhead')
        limits = toolhead.get_status(self.printer.get_reactor().monotonic())
        low, high = limits['axis_minimum'], limits['axis_maximum']
        mesh = self.snapshot['mesh']
        params = mesh.mesh_params
        # Permit the configured rear point as well as the former front point.
        # Axis/mesh bounds do not prove that the part or clips clear this path.
        if (not all(math.isfinite(v) for v in (x, y))
                or not low.x <= x <= high.x or not low.y <= y <= high.y
                or not params['min_x'] <= px <= params['max_x']
                or not params['min_y'] <= py <= params['max_y']):
            raise gcmd.error('Recovery nozzle/probe point is outside the supported geometry')
        rx = self.home_xy[0] + self.snapshot['offsets'][0]
        ry = self.home_xy[1] + self.snapshot['offsets'][1]
        if not (params['min_x'] <= rx <= params['max_x']
                and params['min_y'] <= ry <= params['max_y']):
            raise gcmd.error('Original homing reference is outside the saved mesh')
        if not self.snapshot['hotend'] >= self.printer.lookup_object(
                'configfile').get_status(0.)['settings']['extruder']['min_extrude_temp']:
            raise gcmd.error('The saved print temperature is unsuitable for recovery')
        # probe_finalize() stores bed_z in the original raw homing frame when
        # zero_reference_position is absent. Do NOT subtract calc_z(rx, ry):
        # interpolation there need not be zero. calc_z uses Klipper's final
        # interpolated table, not the nearest raw 5x5 sample.
        correction = mesh.calc_z(px, py)
        bedmesh = self.printer.lookup_object('bed_mesh')
        fade_offset = bedmesh.tool_offset
        self.ready = False
        # Only successful homing clears this latch. RESUME must not retry a
        # failed or interrupted physical sequence; a diagnostic call is explicit.
        self.homing_failed = True
        self.gcode.run_script_from_command('SAVE_GCODE_STATE NAME=FILAMENT_RECOVERY_PARK')
        try:
            bedmesh.set_mesh(None)
            self.raw_home('X')
            self.raw_home('Y')
            # XY-only travel with Z still unhomed: no invented Z coordinate.
            toolhead.manual_move([x, y, None], self.speed)
            self.raw_home('Z')
            toolhead.manual_move([None, None, self.probe_lift], self.speed)
            # The old mesh was measured hot. Establish a new, warm edge
            # reference after restoring temperatures; never mix cold and hot.
            self.reheat()
            self.raw_home('Z')
            pos = toolhead.get_position()
            pos[2] += correction
            toolhead.set_position(pos)
            bedmesh.set_mesh(copy.deepcopy(mesh))
            bedmesh.tool_offset = fade_offset
            self.printer.lookup_object('gcode_move').reset_last_position()
            # Lift at the probe point before any later XY return over the part.
            self.gcode.run_script_from_command(
                'RESTORE_GCODE_STATE NAME=FILAMENT_RECOVERY_PARK')
            park_z = self.park_position[2]
            if not park_z > self.status('gcode_move')['position'].z:
                raise gcmd.error('Recovery park height is not above the probe')
            # manual_move consumes native coordinates; reproduce the original
            # mesh transform once, including fade, without changing PAUSE_STATE.
            z = park_z + bedmesh.get_z_factor(park_z) * (
                mesh.calc_z(x, y) - bedmesh.fade_target) + bedmesh.fade_target
            toolhead.manual_move([None, None, z], self.speed)
            self.printer.lookup_object('gcode_move').reset_last_position()
        except Exception as exc:
            self.gcode.run_script_from_command('TURN_OFF_HEATERS\nM84')
            bedmesh.set_mesh(copy.deepcopy(mesh))
            bedmesh.tool_offset = fade_offset
            raise gcmd.error('Recovery homing failed: %s. Print remains paused; '
                             'inspect before using RECOVER_HOMING or cancel.' % exc) from exc
        self.correction = correction
        self.homing_failed = False
        self.ready = True
        gcmd.respond_info('Recovery homing completed. Check print adhesion, '
                          'print position and toolhead clearance along the return '
                          'path, then press RESUME again to continue.')

    def resume(self, gcmd):
        if self.status('toolhead')['homed_axes'] != 'xyz':
            # Account for reference loss even without a motor_off event.
            if not self.powered_down:
                self.power_off(None)
            self.ready = False
        self.check_pause(gcmd)
        velocity = gcmd.get_float('VELOCITY', self.printer.lookup_object(
            'pause_resume').recover_velocity, above=0.)
        if self.homing_failed:
            raise gcmd.error('Cannot resume: previous recovery homing failed. '
                             'Inspect before using RECOVER_HOMING or cancel; '
                             'RESUME will not repeat the failed motion.')
        if not self.ready:
            if not self.automatic_recovery:
                raise gcmd.error('Cannot resume: recovery homing is required but '
                                 'automatic recovery is disabled until the configured '
                                 'point and paths have been hardware validated.')
            self.gcode.run_script_from_command('RECOVER_HOMING')
            return  # A later, explicit RESUME confirms the requested inspection.
        self.check_mesh(gcmd)
        for name, target in (('heater_bed', self.snapshot['bed']),
                             ('extruder', self.snapshot['hotend'])):
            heater = self.status(name)
            if heater['target'] != target or (target > 0 and abs(heater['temperature'] - target) > 2.):
                raise gcmd.error('Original temperatures are not stable; recovery stopped')
        sensor = self.status('filament_switch_sensor filament_sensor')
        if sensor['enabled'] and not sensor['filament_detected']:
            raise gcmd.error('Insert filament before resuming')
        self.gcode.run_script_from_command('_FILAMENT_RESUME VELOCITY=%.6f' % velocity)


def load_config(config):
    return FilamentRecovery(config)
