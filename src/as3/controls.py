# SPDX-License-Identifier: GPL-3.0-or-later
"""Derive the visual adapters from the official linkage and callback contracts."""

LINKAGES = {
    'radius_bar': (70, 'GunMarkerMixing'),
    'radius_red': (27, 'GunMarkerMixingWithoutProgress'),
    'radius_stapper': (33, 'GunMarkerMixingWithoutProgress'),
    'radiusTtypered': (18, 'GunMarkerMixingWithoutProgress'),
    'radiusTtypestapper': (20, 'GunMarkerMixingWithoutProgress'),
    'continiusLine': (21, 'GunMarkerMixingSolid'),
    'GunMarkerTagUI': (151, 'GunMarkerTag'),
    'GunMarkerSPGUI': (475, 'GunMarkerStrategic'),
    'GunMarkerSPGDebugUI': (476, 'GunMarkerDebugStrategic'),
    'ArtyHitMarkerUI': (990, 'GunMarkerArtillery'),
}


def base(name):
    return 'SolidReticleNative_' + name


def stub(name):
    parent = LINKAGES[name][1]
    return ('package { import net.wg.gui.components.crosshairPanel.components.gunMarker.' + parent
            + '; public class ' + base(name) + ' extends ' + parent + ' {} }\n')


RING = '''
    private var ink:Shape;
    private var progress:Number=0;
    private var bold:Boolean=false;
    private var drawn:Number=NaN;
    private var drawnBold:Boolean;

    override public function setReloadingAsPercent(value:Number, force:Boolean=false):void {
        if (PROGRESS && isFinite(value)) progress=Math.max(0,Math.min(1,value));
        paint();
    }
    override public function setReloadingState(state:String):void {
        var ready:Boolean=state=="reloadingEnded" || state=="reloadingEnd";
        if (!PROGRESS || ready) progress=ready?1:0;
        paint();
    }
    override public function setThickness(value:String):void {
        bold=value=="bold";
        paint();
    }
    private function paint():void {
        if (!ink || (drawn==progress && drawnBold==bold)) return;
        drawn=progress;
        drawnBold=bold;
        SolidReticleArt.ring(ink.graphics,progress,SOLID,bold);
    }
'''

GUN = '''
    private var ink:Shape;
    private var kind:Number=-1;
    private var state:String="normal";
    private var ready:Boolean=false;
    private const colors:Object={red:0xF02311,orange:0xFF9900,green:SolidReticleArt.GREEN,
        yellow:0xFFFF00,purple:0x6064DA,pink:0xCC99FF};

    override public function setType(value:Number):void {
        kind=value;
        super.setType(value);
    }
    override public function setColor(value:String):void {
        state=value;
        super.setColor(value);
    }
    override public function setReloadingState(value:String):void {
        ready=value=="reloadingEnded" || value=="reloadingEnd";
        super.setReloadingState(value);
    }
    override protected function draw():void {
        super.draw();
        if (!ink) return;
        if (tag) tag.visible=false;
        var result:Boolean=kind%3==0 && colors.hasOwnProperty(state);
        var color:uint=result?uint(colors[state]):kind%3==1?(ready?0xC3FF68:0xF02311):SolidReticleArt.WHITE;
        SolidReticleArt.gun(ink.graphics,kind,color,result);
    }
'''

POINTS = '''
    private var drawn:uint;
    override protected function setCurrentReloading(value:Number):void {
        super.setCurrentReloading(value);
        paint(IMPACT || value>=1);
    }
    private function paint(ready:Boolean):void {
        var color:uint=ready?SolidReticleArt.GREEN:0xFF3300;
        if (drawn==color || !_nodes) return;
        drawn=color;
        for each (var node:MovieClip in _nodes) {
            if (!node) continue;
            for (var i:int=0;i<node.numChildren;i++) node.getChildAt(i).visible=false;
            node.filters=[];
            SolidReticleArt.point(node.graphics,color);
        }
    }
'''


def render(name):
    if name == 'GunMarkerTagUI':
        methods = GUN
        init = 'ink=new Shape(); addChild(ink);'
    elif name in ('GunMarkerSPGUI', 'GunMarkerSPGDebugUI', 'ArtyHitMarkerUI'):
        methods = POINTS.replace('IMPACT', str(name == 'ArtyHitMarkerUI').lower())
        init = 'paint(' + str(name == 'ArtyHitMarkerUI').lower() + ');'
    else:
        solid = name == 'continiusLine'
        methods = RING.replace('SOLID', str(solid).lower()).replace('PROGRESS', str(solid or name == 'radius_bar').lower())
        init = ('for (var i:int=0;i<numChildren;i++) getChildAt(i).visible=false; '
                'stop(); ink=new Shape(); addChild(ink); '
                + ('ink.rotation=90; ' if solid else '') + 'paint();')
    return ('package { import flash.display.MovieClip; import flash.display.Shape; public class '
            + name + ' extends ' + base(name) + ' { public function ' + name + '() { super();'
            + init + '}\n' + methods + '\n}}\n')
