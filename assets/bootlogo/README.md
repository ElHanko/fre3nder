# F3 kernel bootlogo source

`f3-portrait.png` is the byte-exact operator-supplied Fre3nder artwork named
`Futuristisches F3-Logo in Cyan.png`, 944x1666 RGB pixels. Its SHA256 is:

```text
1a9248d3d135ed49e6ff4dd4b21fdd6ddff6ae077f532234f5b00748004a7e74
```

The source PNG and its kernel-carried derivative are classified as
`GPL-2.0-only` in `REUSE.toml` and the kernel patch policy.

The prepared 480x272 RGB PNG is carried as a binary replacement of
`module_drivers/drivers/video/logo-ingenic/logo.png` in
`patches/kernel/0005-fre3nder-ender3-v3-ke-integration-v6.6.157.patch`.
Its SHA256 is:

```text
798e7f7fc53da02eff28a5dfea916a23fd54b56096c5217a992f972dc7534847
```

## Preparation

The qualified Screen implementation uses `LV_DISP_ROT_90` with software
rotation: portrait coordinates map to native coordinates as
`(x, y) -> (y, 271 - x)`. This is a 90-degree counterclockwise pixel rotation,
also used by fbcon's `rotate_all=3`. The bootlogo must apply that rotation in
advance because `show_logo()` neither rotates nor scales.

FFmpeg 7.1.5 produced the prepared image with this command, run from the
repository root:

```sh
ffmpeg -hide_banner -loglevel error -i assets/bootlogo/f3-portrait.png \
  -vf "scale=272:480:force_original_aspect_ratio=decrease:flags=lanczos,pad=272:480:(ow-iw)/2:(oh-ih)/2:color=black,lutrgb=r='if(lte(val,16),0,val)':g='if(lte(val,16),0,val)':b='if(lte(val,16),0,val)',transpose=cclock,setsar=1,format=rgb24" \
  -frames:v 1 -c:v png -compression_level 9 -pred mixed -flags +bitexact \
  -threads 1 -map_metadata -1 -y /tmp/fre3nder-f3-480x272.png
```

Lanczos scales to the portrait viewport while preserving aspect ratio; black
padding fills any remaining area. RGB values at or below 16 are set to zero
to remove the supplied image's near-black background noise. The resulting
PNG is opaque RGB, with a black perimeter and preserved cyan/white artwork.

Regenerating the asset also requires refreshing the binary replacement in
patch 0005, its `patch_sha256`, the verified kernel `result_tree`, and the
existing test checksum. Normal kernel builds consume the prepared PNG from
the patch and use the existing `scripts/pic2logo` converter; they do not run
FFmpeg or read the portrait source. No new build or runtime dependency is
introduced.

The new logo is offline-validated, not yet built or hardware-qualified. The
first hardware check must confirm upright presentation, colors and contours,
then the existing tty1 boot output and tty7 Screen handoff.
