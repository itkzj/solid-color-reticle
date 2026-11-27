# coding: utf-8
# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional garage menu for battle-scoped Solid Color Reticle settings."""
from __future__ import absolute_import

from importlib import import_module


_LINKAGE = 'solid_color_reticle'
_OPTIONS = (
    ('minimum', True, '最小落弹环', 'Minimum dispersion ring'),
    ('penetration', True, '穿深计算', 'Penetration calculation'),
    ('glow', True, '发光大十字', 'Glowing cross'),
    ('traverse', True, '射界标尺', 'Gun traverse indicators'),
    ('splash', True, '火炮溅射范围', 'Artillery splash area'),
    ('native_ring', False, '使用游戏默认瞄准环', 'Use game default aiming circle'),
)
_GLOW_SIZE = ('glow_size', 100, 5, 200, 5, '发光大十字大小', 'Glowing cross size')
_GLOW_DISTANCE = ('glow_distance', 5, 0, 100, 1, '发光大十字离中心距离', 'Glowing cross distance from centre')
_SLIDERS = (_GLOW_SIZE, _GLOW_DISTANCE)
_values = {key: default for key, default, _, _ in _OPTIONS}
_values.update((row[0], row[1]) for row in _SLIDERS)
_menu = None
_enabled = None


def snapshot():
    """Capture the settings for a battle without sharing mutable state."""
    return _values.copy()


def _update(settings):
    if isinstance(settings, dict):
        for key, _, _, _ in _OPTIONS:
            value = settings.get(key)
            if isinstance(value, bool):
                _values[key] = value
        for key, _, low, high, step, _, _ in _SLIDERS:
            value = settings.get(key)
            if type(value) in (int, long, float) and low <= value <= high and (value - low) % step == 0:
                _values[key] = int(value)


def _on_save(linkage, settings):
    if linkage == _LINKAGE and _enabled is not None and _enabled():
        _update(settings)


def _chinese():
    try:
        from helpers import getClientLanguage
        language = getClientLanguage().lower().replace('-', '_')
        return language == 'cn' or language.split('_', 1)[0] == 'zh'
    except (ImportError, AttributeError, TypeError):
        return False


def _template(templates, chinese, sliders=_SLIDERS):
    notice = '更改从下一场战斗起生效' if chinese else 'Changes apply next battle'
    controls = [templates.createLabel(notice)]
    enable_when = getattr(templates, 'enableWhen', None)
    for key, default, zh, en in _OPTIONS:
        controls.append(templates.createCheckbox(zh if chinese else en, key, default))
        if key == 'glow':
            for option, value, low, high, step, zh_label, en_label in sliders:
                slider = templates.createSlider(zh_label if chinese else en_label, option,
                                                value, low, high, step, format='{{value}}%')
                controls.append(enable_when(slider, 'glow', True) if enable_when else slider)
    return {
        'modDisplayName': '纯色瞄准' if chinese else 'Solid Color Reticle',
        'column1': controls,
        'column2': [],
    }


def install(log, enabled):
    """Register once with the first available menu and restore its saved values."""
    global _enabled, _menu
    _enabled = enabled
    if _menu is not None:
        menu, template = _menu
        try:
            _update(menu.getModSettings(_LINKAGE, template))
        except Exception:
            log('reload saved reticle settings')
        return

    for name in ('gui.aslainMenu', 'gui.modsSettingsApi'):
        try:
            module = import_module(name)
        except ImportError:
            continue
        except Exception:
            log('import settings menu: ' + name)
            continue
        try:
            chinese = _chinese()
            templates = module.templates
            template = _template(templates, chinese)
            menu = module.g_modsSettingsApi
            previous = None
            if name == 'gui.aslainMenu':
                template['settingsVersion'] = 1
            else:
                # Izeberg matches the whole template, including old slider limits.
                old_size = (_GLOW_SIZE[:2] + (75, 150) + _GLOW_SIZE[4:],)
                for language, sliders in ((not chinese, _SLIDERS), (chinese, old_size),
                                          (not chinese, old_size), (chinese, ()), (not chinese, ())):
                    previous = menu.getModSettings(_LINKAGE, _template(templates, language, sliders))
                    if previous:
                        break
            saved = menu.setModTemplate(_LINKAGE, template, _on_save)
            _update(saved)
            if isinstance(previous, dict) and isinstance(saved, dict):
                # Izeberg returns its live map and queues the write for the next tick.
                _update(previous)
                saved.update(snapshot())
        except Exception:
            log('register settings menu: ' + name)
        else:
            # Neither verified menu has a public unregister method. The callback
            # uses the current lifecycle predicate across fini()/init() cycles.
            _menu = menu, template
            return
