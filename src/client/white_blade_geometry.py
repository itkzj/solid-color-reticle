# coding: utf-8
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only projection for the SPG footprint and horizontal gun limits."""
import math
import BigWorld
import GUI
import Math
from AvatarInputHandler import aih_global_binding, gun_marker_ctrl
from aih_constants import CTRL_MODE_NAME


_NAN = float('nan')


def finite(value):
    return not math.isnan(value) and not math.isinf(value)


def screen(point, width, height, scale):
    matrix = Math.Matrix()
    matrix.setTranslate(point)
    matrix = BigWorld.checkAndRecalculateIfPositionInExtremeProjection(matrix)
    transformed = BigWorld.makeWorldMatrix(width / height, matrix)
    p = transformed.applyV4Point(Math.Vector4(0., 0., 0., 1.))
    if p[3] <= 0 or not all(finite(v) for v in p):
        return None
    return ((p[0] / p[3] + 1.) * .5 * width / scale,
            (1. - p[1] / p[3]) * .5 * height / scale)


def _spg_traverse_axis(rotator, width, height, scale):
    # bindRO returns the observable on class access, and the value on instance access.
    binding = Geometry.server if gun_marker_ctrl.useServerGunMarker() else Geometry.client
    provider = binding.value
    if provider is None or not finite(height) or height <= 0:
        return None
    origin, velocity = rotator.getCurShotPosition()
    speed = math.hypot(velocity.x, velocity.z)
    if not finite(speed) or speed <= 0:
        return None
    point = Math.Matrix(provider.positionMatrixProvider).translation
    distance = math.hypot(point.x - origin.x, point.z - origin.z)
    shot_x, shot_z = velocity.x / speed, velocity.z / speed
    # Project the local forward and lateral ground directions at the aim marker.
    centre = screen(point, width, height, scale)
    forward = screen(point + Math.Vector3(shot_x, 0., shot_z), width, height, scale)
    lateral = screen(point + Math.Vector3(shot_z, 0., -shot_x), width, height, scale)
    if centre is None or forward is None or lateral is None:
        return None
    dx, dy = forward[0] - centre[0], forward[1] - centre[1]
    length = math.hypot(dx, dy)
    if not finite(length) or length <= 1e-6:
        return None
    # Use only the lateral component perpendicular to the projected shot line.
    pixels_per_metre = abs(-dy * (lateral[0] - centre[0]) + dx * (lateral[1] - centre[1])) / length
    units_per_radian = distance * pixels_per_metre
    if not finite(units_per_radian) or units_per_radian <= 0:
        return None
    return math.degrees(math.atan2(dx, -dy)), units_per_radian


def traverse(panel, vehicle):
    empty = (_NAN,) * 5
    if vehicle is None or vehicle.health <= 0:
        return empty
    descriptor = vehicle.typeDescriptor
    if descriptor.gun.turretYawLimits is None:
        return empty
    player = BigWorld.player()
    if player is None or player.getVehicleAttached() is not vehicle:
        return empty
    handler = player.inputHandler
    if handler.ctrlModeName not in (CTRL_MODE_NAME.ARCADE, CTRL_MODE_NAME.SNIPER,
                                    CTRL_MODE_NAME.STRATEGIC, CTRL_MODE_NAME.ARTY):
        return empty
    rotator = player.gunRotator
    limits = rotator._VehicleGunRotator__getTurretYawLimits()
    if limits is None:
        return empty
    left, right = limits
    if not (finite(left) and finite(right) and left <= right):
        return empty
    yaw = rotator.turretYaw
    if not finite(yaw):
        return empty
    half_span = (right - left) * .5
    # Unwrap about the actual midpoint, including asymmetric and rear-facing limits.
    relative = (yaw - (left + half_span) + math.pi) % (2 * math.pi) - math.pi
    # Use the last 0.5 degrees, capped for very narrow arcs, as the red warning zone.
    warning = min(math.radians(.5), half_span * .1)
    fade_span = half_span - warning

    width, height = map(float, GUI.screenResolution())
    scale = float(panel.getScale())
    if not all(finite(v) and v > 0 for v in (width, scale)):
        return empty
    scale = max(1., scale)
    rotation = 0.
    # Let the viewport clip the arrows naturally even when the aim centre is offset.
    units_per_radian = width / (scale * math.pi)
    if handler.ctrlModeName in (CTRL_MODE_NAME.STRATEGIC, CTRL_MODE_NAME.ARTY):
        axis = _spg_traverse_axis(rotator, width, height, scale)
        if axis is None:
            return empty
        rotation, units_per_radian = axis
    positions = []
    ratios = []
    for side, distance in ((-1., half_span + relative), (1., half_span - relative)):
        offset = 0. if distance <= 1e-9 else distance * units_per_radian
        positions.append(side * offset)
        # Green from the midpoint onward, also when the native limits coincide.
        if distance >= half_span:
            ratio = 1.
        elif distance <= warning:
            ratio = 0.
        else:
            ratio = (distance - warning) / fade_span
        ratios.append(ratio)
    return positions[0], positions[1], ratios[0], ratios[1], rotation


class Geometry(object):
    client = aih_global_binding.bindRO(aih_global_binding.BINDING_ID.CLIENT_SPG_GUN_MARKER_DATA_PROVIDER)
    server = aih_global_binding.bindRO(aih_global_binding.BINDING_ID.SERVER_SPG_GUN_MARKER_DATA_PROVIDER)

    def sample(self, panel, splash):
        empty = dict(height=float('nan'), splashPixels=float('nan'), splashRadiusX=float('nan'),
                     splashRadiusY=float('nan'), splashRotation=float('nan'), splashX=0., splashY=0.)
        player = BigWorld.player()
        if player is None or player.inputHandler.ctrlModeName not in (CTRL_MODE_NAME.STRATEGIC, CTRL_MODE_NAME.ARTY):
            return empty
        provider = self.server if gun_marker_ctrl.useServerGunMarker() else self.client
        if provider is None:
            return empty
        point = Math.Matrix(provider.positionMatrixProvider).translation
        camera = Math.Matrix(BigWorld.camera().invViewMatrix)
        empty['height'] = abs(camera.translation.y - point.y)
        if not finite(splash) or splash <= 0:
            return empty
        width, height = map(float, GUI.screenResolution())
        scale = float(panel.getScale())
        if not all(finite(v) and v > 0 for v in (width, height, scale)):
            return empty
        centre = screen(point, width, height, scale)
        ground_x = screen(point + Math.Vector3(1., 0., 0.) * splash, width, height, scale)
        ground_z = screen(point + Math.Vector3(0., 0., 1.) * splash, width, height, scale)
        if centre is None or ground_x is None or ground_z is None:
            return empty
        ex = (ground_x[0] - centre[0], ground_x[1] - centre[1])
        ez = (ground_z[0] - centre[0], ground_z[1] - centre[1])
        xx = ex[0] * ex[0] + ez[0] * ez[0]
        xy = ex[0] * ex[1] + ez[0] * ez[1]
        yy = ex[1] * ex[1] + ez[1] * ez[1]
        trace = xx + yy
        delta = math.sqrt(max(0., (xx - yy) * (xx - yy) + 4. * xy * xy))
        major = math.sqrt(max(0., (trace + delta) * .5))
        minor = math.sqrt(max(0., (trace - delta) * .5))
        angle = .5 * math.atan2(2. * xy, xx - yy)
        anchor = panel.sessionProvider.shared.crosshair.getScaledPosition()
        if finite(major) and finite(minor) and major > 0 and minor > 0:
            empty.update(splashPixels=major, splashRadiusX=major, splashRadiusY=minor,
                         splashRotation=angle * 180. / math.pi,
                         splashX=centre[0]-anchor[0], splashY=centre[1]-anchor[1])
        return empty
