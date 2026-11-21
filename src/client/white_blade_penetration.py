# SPDX-License-Identifier: GPL-3.0-or-later
"""Estimate penetration for a selected World of Tanks PC impact path.

Armour and penetration are in mm. Travel is in m. The caller supplies game
collision geometry and the state of the currently loaded shot.
"""
from collections import namedtuple
from math import acos, cos, degrees, erf, isinf, isnan, radians, sqrt


Shell = namedtuple('Shell', 'kind caliber_mm pen_near_mm pen_far_mm max_range_m')


class Layer(namedtuple('LayerBase', 'kind thickness_mm cosine gap_before_m '
                       'use_hit_angle check_caliber_norm may_ricochet he_stops check_caliber_ricochet')):
    __slots__ = ()

    def __new__(cls, kind, thickness_mm, cosine, gap_before_m, use_hit_angle=True,
                check_caliber_norm=True, may_ricochet=True, he_stops=False,
                check_caliber_ricochet=True):
        return super(Layer, cls).__new__(cls, kind, thickness_mm, cosine, gap_before_m,
                                         use_hit_angle, check_caliber_norm, may_ricochet,
                                         he_stops, check_caliber_ricochet)


Result = namedtuple('Result', 'armor_mm penetration_probability ricochet')

_WOT_SHELLS = {'AP': (5.0, 70.0), 'APCR': (2.0, 70.0), 'HEAT': (0.0, 85.0),
               'HE': (0.0, None)}
_LAYER_TYPES = ('armor', 'screen', 'external', 'destructible')
_MAX_HIT_ANGLE = radians(90.0) - 1e-5
_GAUSSIAN_SCALE = 0.33 * sqrt(2.0)


def _number(value, name, minimum=0.0, maximum=float('inf')):
    if isinstance(value, (bool, str, bytes)):
        raise ValueError('%s must be a number' % name)
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError('%s must be a finite number' % name)
    if isnan(value) or isinf(value) or not minimum <= value <= maximum:
        raise ValueError('%s is out of range' % name)
    return value


def _mean_pen_at(shell, distance, multiplier, anchors):
    pen_near = _number(shell.pen_near_mm, 'penetration at first distance anchor')
    pen_far = _number(shell.pen_far_mm, 'penetration at second distance anchor')
    near, far = anchors
    if distance <= near or near == far:
        return pen_near * multiplier
    t = (distance - near) / (far - near)
    return max(0.0, pen_near + (pen_far - pen_near) * t) * multiplier


def _probability(required, mean, low, high):
    # ponytail: garage CDF shape with bounded rolls; replace with a verified server distribution.
    if high == low:
        return float(high > required)
    if required <= low:
        return 1.0
    if required >= high:
        return 0.0
    width = high - mean if required > mean else mean - low
    if required == mean:
        return 0.5
    return 0.5 * (1.0 + erf(((mean - required) / width) / _GAUSSIAN_SCALE))


def calculate(shell, distance_m, layers, piercing_multiplier=1.0, rng_bounds=(0.75, 1.25),
              distance_anchors_m=(50.0, 500.0), normalization_deg=None, ricochet_cos=None,
              heat_loss_per_m=0.5):
    """Predict first-path impact for AP, APCR, HEAT and ordinary direct-fire HE.

    Supply ordered, deduplicated game collision layers. Distance is to the
    first collision. For HEAT, gap_before_m is travel from the previous
    collision point minus that layer's nominal thickness in metres. The
    first gap is zero. Supply live overrides when the game changes the shot.
    """
    if not isinstance(shell, Shell) or shell.kind not in _WOT_SHELLS:
        raise ValueError('expected Shell with kind AP, APCR, HEAT or HE')
    caliber = _number(shell.caliber_mm, 'caliber')
    maximum = _number(shell.max_range_m, 'maximum range')
    distance = _number(distance_m, 'distance')
    multiplier = _number(piercing_multiplier, 'piercing multiplier')
    if not caliber or not maximum:
        raise ValueError('caliber and maximum range must be positive')
    lower, upper = rng_bounds
    lower = _number(lower, 'lower penetration multiplier', 0.0, 1.0)
    upper = _number(upper, 'upper penetration multiplier', 1.0)
    near, far = distance_anchors_m
    near = _number(near, 'first distance anchor')
    far = _number(far, 'second distance anchor', near)
    heat_loss = _number(heat_loss_per_m, 'HEAT loss per metre')
    base_norm, bounce_angle = _WOT_SHELLS[shell.kind]
    kinetic = shell.kind in ('AP', 'APCR')
    heat = shell.kind == 'HEAT'
    he = shell.kind == 'HE'
    if normalization_deg is not None:
        base_norm = _number(normalization_deg, 'normalization angle', 0.0, 90.0 if kinetic else 0.0)
    bounce_cos = None if he else cos(radians(bounce_angle))
    if ricochet_cos is not None:
        if he:
            raise ValueError('ordinary HE has no ricochet angle')
        bounce_cos = _number(ricochet_cos, 'ricochet cosine', 0.0, 1.0)

    layers = tuple(layers)
    for index, layer in enumerate(layers):
        if not isinstance(layer, Layer) or layer.kind not in _LAYER_TYPES:
            raise ValueError('expected Layer with known collision kind')
        if _number(layer.thickness_mm, 'nominal thickness') <= 0:
            raise ValueError('nominal thickness must be positive')
        _number(layer.cosine, 'incidence cosine', 0.0, 1.0)
        if _number(layer.gap_before_m, 'gap length') and index == 0:
            raise ValueError('first layer must have zero gap')
        if not all(isinstance(flag, bool) for flag in layer[4:]):
            raise ValueError('layer material flags must be booleans')

    mean = _mean_pen_at(shell, distance, multiplier, (near, far))
    if distance >= maximum:
        return Result(None, 0.0, False)
    high = _number(mean * upper, 'upper penetration roll')
    low = mean * lower
    armor_mm = None

    # Remaining penetration = scale * initial roll - loss.
    scale, loss, required = 1.0, 0.0, -float('inf')
    heat_triggered = False
    for layer in layers:
        thickness = float(layer.thickness_mm)
        cosine = float(layer.cosine)
        if heat_triggered:
            gap_scale = max(0.0, 1.0 - heat_loss * float(layer.gap_before_m))
            scale *= gap_scale
            loss *= gap_scale
            if not scale:
                return Result(armor_mm, 0.0, False)
        angle = acos(cosine)
        anti_ricochet = kinetic and layer.check_caliber_ricochet and caliber > 3.0 * thickness
        use_angle = layer.use_hit_angle and layer.kind != 'destructible'
        hit_cosine = cosine if use_angle else 1.0
        bounces = (layer.kind != 'destructible' and layer.may_ricochet and not he
                   and not heat_triggered and not anti_ricochet and hit_cosine <= bounce_cos)
        effective = thickness
        normalization = 0.0
        if use_angle:
            normalization = radians(base_norm)
            if kinetic and layer.check_caliber_norm and caliber > 2.0 * thickness:
                normalization *= 1.4 * (caliber / thickness) / 2.0
            normalization = min(angle, normalization)
            corrected = min(_MAX_HIT_ANGLE, angle - normalization)
            effective = thickness / max(cos(corrected), 1e-5)

        if bounces:
            reaches_layer = _probability(required, mean, low, high) > 0
            return Result(effective, 0.0, reaches_layer)

        required = max(required, (loss + effective) / scale)
        armor_mm = required
        probability = _probability(required, mean, low, high)
        if layer.kind == 'armor':
            return Result(armor_mm, probability, False)
        if not probability or (he and layer.he_stops):
            return Result(armor_mm, 0.0, False)

        loss += effective * (3.0 if he and layer.kind in ('screen', 'external') else 1.0)
        if heat and layer.kind in ('screen', 'external'):
            heat_triggered = True

    return Result(armor_mm, 0.0, False)


_SHOT_KINDS = {'ARMOR_PIERCING': 'AP', 'ARMOR_PIERCING_CR': 'APCR',
               'HOLLOW_CHARGE': 'HEAT', 'HIGH_EXPLOSIVE': 'HE'}


def estimate(marker, player, trace, multiplier, anchors, modern_he):
    """Adapt the client's already-resolved single-vehicle marker collision."""
    descriptor = player.getVehicleDescriptor()
    installation = descriptor.gunInstallations[marker.gunInstallationIndex]
    shot = descriptor.shot if installation.isMainInstallation() else installation.gun.shots[0]
    shell, shell_type = shot.shell, shot.shell.type
    kind = _SHOT_KINDS.get(shell.kind)
    if kind is None or (kind == 'HE' and shell_type.mechanics != modern_he):
        return None
    distance = (marker.position - player.getOwnVehiclePosition()).length
    if distance >= shot.maxDistance:
        return None

    # The native trace provides ordered entry hits and already resolves each material.
    details = trace(marker.position, marker.direction, marker.collData.entity)
    layers, ignored = [], set()
    previous_dist, previous_thickness = 0.0, 0.0
    for hit in details or ():
        material = hit.matInfo
        if material is None:
            return None
        key = (hit.compName, material.kind)
        if key in ignored:
            continue
        if material.collideOnceOnly:
            ignored.add(key)
        if material.armor <= 0 and material.vehicleDamageFactor <= 0:
            continue
        gap = max(0.0, hit.dist - previous_dist - previous_thickness * .001) if layers else 0.0
        armor = material.vehicleDamageFactor > 0
        layers.append(Layer('armor' if armor else 'screen', material.armor, abs(hit.hitAngleCos), gap,
                            bool(material.useHitAngle), bool(material.checkCaliberForHitAngleNorm),
                            bool(material.mayRicochet), kind == 'HE' and not shell_type.shieldPenetration,
                            bool(material.checkCaliberForRicochet)))
        previous_dist, previous_thickness = hit.dist, material.armor
        if armor:
            break

    rng = shell.piercingPowerRandomization
    result = calculate(Shell(kind, shell.caliber, shot.piercingPower[0], shot.piercingPower[1], shot.maxDistance),
                       distance, layers, piercing_multiplier=multiplier, rng_bounds=(1-rng, 1+rng),
                       distance_anchors_m=anchors,
                       normalization_deg=degrees(shell_type.normalizationAngle) if kind in ('AP', 'APCR') else None,
                       ricochet_cos=shell_type.ricochetAngleCos if kind != 'HE' else None,
                       heat_loss_per_m=shell_type.piercingPowerLossFactorByDistance if kind == 'HEAT' else 0.0)
    if result.armor_mm is None:
        return None
    if result.ricochet:
        return result.armor_mm, -1, 0x6064DA
    p = result.penetration_probability
    chance = min(99, max(1, int(round(p * 100)))) if 0 < p < 1 else int(p * 100)
    return result.armor_mm, chance, _chance_color(chance)


def _chance_color(chance):
    red, amber, green = 0xFF3B30, 0xFFD24A, 0x7FFF36
    start, end = (red, amber) if chance <= 50 else (amber, green)
    position = (chance if chance <= 50 else chance - 50) / 50.0
    color = 0
    for shift in (16, 8, 0):
        first, last = (start >> shift) & 255, (end >> shift) & 255
        color |= int(round(first + (last - first) * position)) << shift
    return color
