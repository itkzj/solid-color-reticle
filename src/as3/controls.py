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
    'GunMarkerUI': (468, 'GunMarker'),
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
    private var startProgress:Number=0;
    private var startTime:Number=0;
    private var bold:Boolean=false;
    private var current:Number=NaN;
    private var drawn:Number=NaN;
    private var drawnBold:Boolean;

    override public function setReloadingAsPercent(value:Number, force:Boolean=false):void {
        if (!PROGRESS || !isFinite(value)) return;
        var next:Number=Math.max(0,Math.min(1,value));
        if (force || next<progress) {
            snap(next);
        } else if (next!=progress) {
            startProgress=isFinite(current)?current:progress;
            startTime=getTimer();
            progress=next;
            addEventListener(Event.ENTER_FRAME,onFrame);
        }
    }
    override public function setReloadingState(state:String):void {
        var ready:Boolean=state=="reloadingEnded" || state=="reloadingEnd";
        if (!PROGRESS || state!="reloadingProgress") snap(ready?1:0);
    }
    override public function setThickness(value:String):void {
        bold=value=="bold";
        paint(isFinite(current)?current:progress);
    }
    private function snap(value:Number):void {
        progress=value;
        removeEventListener(Event.ENTER_FRAME,onFrame);
        paint(value);
    }
    private function onFrame(event:Event):void {
        var t:Number=Math.max(0,Math.min(1,(getTimer()-startTime)/90));
        if (t==1) snap(progress);
        else paint(startProgress+(progress-startProgress)*t);
    }
    private function paint(value:Number=0):void {
        if (!ink) return;
        current=value;
        var key:Number=SolidReticleArt.ringProgress(value,SOLID);
        if (drawn==key && drawnBold==bold) return;
        drawn=key;
        drawnBold=bold;
        SolidReticleArt.ring(ink.graphics,value,SOLID,bold);
    }
'''

GUN = '''
    private var ink:Shape;
    private var blade:Shape;
    private var drawnKind:Number=NaN;
    private var drawnColor:uint;
    private var bladeColor:Number=NaN;
    private var kind:Number=-1;
    private var state:String="normal";
    private var ready:Boolean=false;
    private const colors:Object={red:0xF02311,orange:0xFF9900,green:SolidReticleArt.GREEN,
        yellow:0xFFFF00,purple:0x6064DA,pink:0xCC99FF};

    override public function setType(value:Number):void {
        kind=value;
        super.setType(value);
    }
    private var aimColor:Number=NaN;
    override public function setColor(value:String):void {
        if (state==value) return;
        state=value;
        aimColor=/^wb[0-9a-f]{6}$/.test(value)?parseInt(value.substr(2),16):NaN;
        // Only native color names are Timeline labels.
        super.setColor(isNaN(aimColor)?value:"normal");
        invalidate();
    }
    override public function setReloadingState(value:String):void {
        ready=value=="reloadingEnded" || value=="reloadingEnd";
        super.setReloadingState(value);
    }
    override protected function draw():void {
        super.draw();
        if (!ink) return;
        if (tag) tag.visible=false;
        var hasAim:Boolean=!isNaN(aimColor);
        var result:Boolean=kind%3==0 && (hasAim || colors.hasOwnProperty(state));
        var color:uint=result?(hasAim?uint(aimColor):uint(colors[state])):kind%3==1?(ready?0xC3FF68:0xF02311):SolidReticleArt.WHITE;
        if (blade.visible!=result) blade.visible=result;
        if (result && bladeColor!=color) {
            bladeColor=color;
            var red:uint=(color>>16)&255, green:uint=(color>>8)&255, blue:uint=color&255;
            blade.transform.colorTransform=new ColorTransform((255-red)/255,(240-green)/255,
                (186-blue)/255,1,red,green,blue);
        }
        if (drawnKind!=kind || drawnColor!=color) {
            drawnKind=kind;
            drawnColor=color;
            SolidReticleArt.gun(ink.graphics,kind,color);
        }
    }
'''

MINIMUM = '''
    override public function setScale(value:Number):void {
        super.setScale(value);
        if (name.indexOf("solidReticleMinimum")==0) {
            gunTag.visible=false;
            aimDamage.visible=false;
        }
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
        init = ('blade=new Shape(); SolidReticleArt.drawBlades(blade.graphics); blade.visible=false; '
                'addChild(blade); ink=new Shape(); addChild(ink);')
    elif name == 'GunMarkerUI':
        methods = MINIMUM
        init = ''
    elif name in ('GunMarkerSPGUI', 'GunMarkerSPGDebugUI', 'ArtyHitMarkerUI'):
        methods = POINTS.replace('IMPACT', str(name == 'ArtyHitMarkerUI').lower())
        init = 'paint(' + str(name == 'ArtyHitMarkerUI').lower() + ');'
    else:
        solid = name == 'continiusLine'
        methods = RING.replace('SOLID', str(solid).lower()).replace('PROGRESS', str(solid or name == 'radius_bar').lower())
        init = ('for (var i:int=0;i<numChildren;i++) getChildAt(i).visible=false; '
                'stop(); ink=new Shape(); addChild(ink); '
                + ('ink.rotation=90; ' if solid else '') + 'paint();')
    return ('package { import flash.display.MovieClip; import flash.display.Shape; import flash.geom.ColorTransform; '
            'import flash.events.Event; import flash.utils.getTimer; public class '
            + name + ' extends ' + base(name) + ' { public function ' + name + '() { super();'
            + init + '}\n' + methods + '\n}}\n')
