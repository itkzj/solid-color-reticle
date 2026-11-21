// SPDX-License-Identifier: GPL-3.0-or-later
package {
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.display.Graphics;
    import flash.display.LineScaleMode;
    import flash.display.CapsStyle;
    import flash.display.JointStyle;
    import flash.text.TextField;
    import flash.text.TextFormat;
    import flash.text.TextFieldAutoSize;
    import flash.text.AntiAliasType;
    import flash.filters.GlowFilter;
    import flash.utils.getTimer;

    // Shared by arcade, sniper and strategic; coordinates are relative to aim centre.
    public class WhiteBladeHUD extends Sprite {
        private const WHITE:uint=0xF7FAFF, CYAN:uint=0x65E8FF, GREEN:uint=0x7FFF36, RED:uint=0xFF5555;
        private const MUTED:uint=0xDFE7EC, AMBER:uint=0xFFCB66, ORANGE:uint=0xFF9900;
        private var rails:Shape=new Shape();
        private var charge:Sprite=new Sprite();
        private var core:Shape=new Shape();
        private var marks:Shape=new Shape();
        private var arrows:Shape=new Shape();
        private var footprint:Shape=new Shape();
        private var fields:Object={};
        // Move each bar midpoint (230) inward by one quarter; retain both segment lengths.
        private const RAIL_OUTER:Number=257.5, RAIL_INNER:Number=87.5, RAIL_HORIZONTAL:Number=170;
        private const RAIL_LENGTH:Number=538/3;
        public var data:Object={remaining:NaN,total:NaN,progress:NaN,reloadState:"",health:NaN,maxHealth:NaN,healthRatio:NaN,
            distance:"",zoom:"",ammo:NaN,capacity:1,loaded:NaN,burstSize:1,burstTime:NaN,
            aimArmor:NaN,aimChance:NaN,aimColor:NaN,
            penetration:NaN,shell:"",height:NaN,splash:0,splashRadiusX:NaN,splashRadiusY:NaN,splashRotation:NaN,splashX:0,splashY:0,flight:NaN,arty:false,
            traverseLeft:NaN,traverseRight:NaN,traverseLeftRatio:NaN,traverseRightRatio:NaN,traverseRotation:0,
            centerType:0,centerOpacity:1,reloadOpacity:1,healthOpacity:1,clipOpacity:1,timeOpacity:1};
        private var previous:Object={};
        private var motion:Object={};
        private var railState:Array;
        private var markState:Array;
        private var drawnReloadOpacity:Number=NaN;
        private function sameNumbers(a:Array,b:Array):Boolean {
            if(!a || a.length!=b.length)return false;
            for(var i:int=0;i<b.length;i++)if(a[i]!==b[i])return false;
            return true;
        }
        private function changed():Object {
            var dirty:Object=null;
            for(var key:String in data) {
                var value:*=data[key], old:*=previous[key];
                if(value===old || (value is Number && old is Number && isNaN(value) && isNaN(old)))continue;
                previous[key]=value;
                if(!dirty)dirty={};
                dirty[key]=true;
            }
            return dirty;
        }
        // Sampled values stay in data. Each moving layer starts from its last drawn frame.
        private function frame(id:String, target:Array, now:Number, duration:Number,
                               snap:Boolean=false, turn:Number=0):Array {
            var track:Object=motion[id];
            if(!track || !sameNumbers(track.target,target)) {
                var start:Array=track?track.value.slice():[];
                if(snap || start.length!=target.length)start=target;
                if(id=="traverse" && start!=target) {
                    if(target[0]==0)start[0]=0;
                    if(target[1]==0)start[1]=0;
                    if(target[2]==0)start[2]=0;
                    if(target[3]==0)start[3]=0;
                }
                motion[id]=track={target:target,value:start,start:start,time:now,last:NaN};
            }
            if(track.last==now || (track.value===track.target && isFinite(track.last)))return null;
            var t:Number=clamp((now-track.time)/duration);
            track.last=now;
            if(t==1 || track.start===track.target)track.value=track.target;
            else {
                var next:Array=[];
                for(var i:int=0;i<target.length;i++) {
                    var delta:Number=track.target[i]-track.start[i];
                    if(turn && i==target.length-1)delta-=turn*Math.round(delta/turn);
                    next.push(track.start[i]+delta*t);
                }
                track.value=next;
            }
            return track.value;
        }
        public function WhiteBladeHUD(arty:Boolean=false) {
            super();mouseEnabled=false;mouseChildren=false;data.arty=arty;
            addChild(footprint);addChild(rails);addChild(charge);addChild(marks);addChild(arrows);
            charge.addChild(core);
            // Explicit 1-unit backing on all geometry; no additional blurred outline.
            field("remaining",-RAIL_OUTER,-18,20,CYAN,"left");field("health",RAIL_OUTER,-18,20,WHITE,"right");
            field("total",-RAIL_OUTER,14,14,MUTED,"left");field("penetration",RAIL_OUTER,14,14,MUTED,"right");
            var distanceSize:Number=20;
            field("distance",0,-185,distanceSize,WHITE);field("zoom",0,-153,14,MUTED);
            field("height",0,-122,14,MUTED);field("flight",0,-91,arty?distanceSize:14,MUTED);
            field("ammo",0,176,20,WHITE);field("splash",0,80,14,arty?ORANGE:AMBER);
            if(!arty) {
                field("aimArmor",0,185,20,WHITE);
                fields.aimArmor.visible=false;
            }
            if(arty) {
                for each(var id:String in ["remaining","health","total","penetration"]) {
                    var format:TextFormat=fields[id].defaultTextFormat;format.align="center";fields[id].defaultTextFormat=format;
                }
                fields.remaining.x=-200-fields.remaining.width/2;fields.remaining.y=-124;
                fields.health.x=200-fields.health.width/2;fields.health.y=-124;
                fields.total.x=fields.remaining.x;
                fields.penetration.x=fields.health.x;
                fields.distance.y=-177;fields.height.y=-145;
            }
        }
        private function field(id:String,x:Number,y:Number,size:Number,color:uint,align:String="center"):void {
            var t:TextField=new TextField();t.selectable=false;t.mouseEnabled=false;
            t.defaultTextFormat=new TextFormat("$FieldFont",size,color,true,null,null,null,null,align);
            // Fixed fields keep left/right endpoint anchors when their content changes.
            t.autoSize=TextFieldAutoSize.NONE;t.wordWrap=false;t.multiline=false;
            t.width=255;t.height=size+12;t.x=x-(align=="left"?0:align=="right"?t.width:t.width/2);t.y=y-size*.65;
            // Text keeps V11's independent soft outline; geometry uses its own backing.
            t.filters=[new GlowFilter(0x10181E,1,2,2,3,1)];
            t.antiAliasType=AntiAliasType.ADVANCED;addChild(t);fields[id]=t;
        }
        private function mirrorField(top:TextField,bottom:TextField):void {
            // TextField adds a 2px gutter on each side of its text.
            bottom.y=-top.y-4-(top.textHeight+bottom.textHeight)/2;
        }
        private function mirroredCenterY(top:TextField,fallback:TextField):Number {
            // Reserve the row using a same-size label when the game clears the readout.
            var height:Number=top.text?top.textHeight:fallback.textHeight;
            return -top.y-2-height/2;
        }
        private function aimCenterY():Number {
            return mirroredCenterY(fields.distance,fields.health);
        }
        public function clipCenterY():Number {
            if(!data.arty)return mirroredCenterY(fields.zoom,fields.total);
            return aimCenterY();
        }
        private function number(v:Number,digits:int=0,unit:String=""):String {
            return isFinite(v)&&v>=0?v.toFixed(digits)+unit:"—";
        }
        private function put(id:String,value:String):void {if(fields[id].text!=value)fields[id].text=value;}
        private function clamp(v:Number):Number {return isFinite(v)?Math.max(0,Math.min(1,v)):0;}
        private function mix(a:uint,b:uint,t:Number):uint {
            var r:int=Math.round((a>>16)+((b>>16)-(a>>16))*t);
            var g:int=Math.round(((a>>8)&255)+(((b>>8)&255)-((a>>8)&255))*t);
            var blue:int=Math.round((a&255)+((b&255)-(a&255))*t);
            return (r<<16)|(g<<8)|blue;
        }
        private function healthColor(v:Number):uint {
            v=clamp(v);
            return v<=.5?mix(0xFF3B30,0xFFD24A,v*2):mix(0xFFD24A,GREEN,(v-.5)*2);
        }
        private function hpRatio():Number {
            return isFinite(data.health)&&isFinite(data.maxHealth)&&data.maxHealth>0?
                clamp(data.health/data.maxHealth):clamp(data.healthRatio);
        }
        // Native END/ENDED, not the timer: at Ready the native timer contains base reload time.
        private function ready():Boolean {
            return (data.reloadState=="reloadingEnd"||data.reloadState=="reloadingEnded") && data.ammo!=0;
        }
        public function setReloadState(value:String):void {
            data.reloadState=value;
            if(ready())data.progress=1;
            else if(value!="reloadingProgress")data.progress=0;
        }
        public function setReloadPercent(value:Number):void {
            // The native container calls time -> percent -> state (0..1; Ready may also send 100).
            if(isFinite(value)&&value<1&&ready())data.reloadState="reloadingProgress";
            data.progress=isFinite(value)?clamp(value):NaN;
        }
        public function setStock(total:Number,loaded:Number):void {
            // setAmmoStock.state is a cassette animation label, not a gun-ready/shot flag.
            var spent:Boolean=(isFinite(total)&&total>=0&&isFinite(data.ammo)&&total<data.ammo) ||
                (isFinite(loaded)&&loaded>=0&&isFinite(data.loaded)&&loaded<data.loaded);
            data.ammo=isFinite(total)&&total>=0?total:NaN;
            data.loaded=isFinite(loaded)&&loaded>=0?loaded:NaN;
            if(spent||data.ammo==0) {
                data.progress=0;data.remaining=NaN;
                data.reloadState=data.ammo==0?"reloadingImpossibleAmmoEnded":"reloadingProgress";
            }
        }
        private function reloadCharge():Number {
            return ready()?1:data.reloadState=="reloadingProgress"?clamp(data.progress):0;
        }
        public function clipGroups():int {
            return isFinite(data.capacity)&&data.capacity>1&&isFinite(data.burstSize)?
                Math.ceil(data.capacity/Math.max(1,data.burstSize)):0;
        }
        private function railPoint(s:Number):Array {
            var r:Number=1,h:Number=RAIL_HORIZONTAL;
            if(s<=h-r)return [RAIL_OUTER-s,0];
            if(s>=h+r)return [RAIL_INNER,s-h];
            var t:Number=(s-h+r)/(2*r);
            return [RAIL_INNER+r*(1-t)*(1-t),r*t*t];
        }
        private function rail(g:Graphics,side:Number,from:Number,to:Number,color:uint,width:Number,opacity:Number):void {
            var a:Number=clamp(from)*RAIL_LENGTH,b:Number=clamp(to)*RAIL_LENGTH;
            if(b<=a||opacity<=0)return;
            // Keep endpoints and HP's original logical travel; a quadratic rounds both corner edges.
            var h:Number=RAIL_HORIZONTAL,r:Number=1,p:Array=railPoint(a);
            g.lineStyle(width,color,clamp(opacity),false,LineScaleMode.NORMAL,CapsStyle.ROUND,JointStyle.ROUND);
            g.moveTo(side*p[0],p[1]);
            if(a<h-r&&b>h-r)g.lineTo(side*(RAIL_INNER+r),0);
            if(a<h+r&&b>h-r) {
                var u:Number=Math.max(a,h-r),v:Number=Math.min(b,h+r);
                var t:Number=(u-h+r)/(2*r),dt:Number=(v-u)/(2*r);
                p=railPoint(u);var end:Array=railPoint(v);
                g.curveTo(side*(p[0]-r*(1-t)*dt),p[1]+r*t*dt,side*end[0],end[1]);
            }
            if(b<=h-r||b>h+r) {p=railPoint(b);g.lineTo(side*p[0],p[1]);}
        }
        private function artyRail(g:Graphics,side:Number,progress:Number,color:uint,width:Number,opacity:Number):void {
            if(opacity<=0||!isFinite(progress)||progress<=0)return;
            // Equal normal stroke width on every segment; trim one unit around each bend.
            var diagonal:Number=Math.sqrt(18*18+26*26),dx:Number=18/diagonal,dy:Number=26/diagonal;
            var points:Array=[[182,84],[200-dx,58+dy],[200,57],[200,-57],[200-dx,-58-dy],[182,-84]];
            var lengths:Array=[diagonal-1,2,114,2,diagonal-1];
            var left:Number=clamp(progress)*(2*diagonal+116);
            g.lineStyle(width,color,clamp(opacity),false,LineScaleMode.NORMAL,CapsStyle.ROUND,JointStyle.ROUND);
            g.moveTo(side*182,84);
            for(var i:int=0;i<lengths.length&&left>0;i++) {
                var t:Number=Math.min(1,left/lengths[i]),a:Array=points[i],b:Array=points[i+1];
                if(i==1||i==3) {
                    var cy:Number=i==1?58:-58;
                    var ex:Number=(1-t)*(1-t)*a[0]+2*(1-t)*t*200+t*t*b[0];
                    var ey:Number=(1-t)*(1-t)*a[1]+2*(1-t)*t*cy+t*t*b[1];
                    g.curveTo(side*(a[0]+t*(200-a[0])),a[1]+t*(cy-a[1]),side*ex,ey);
                } else g.lineTo(side*(a[0]+(b[0]-a[0])*t),a[1]+(b[1]-a[1])*t);
                left-=lengths[i];
            }
        }
        private function shell(g:Graphics,x:Number,y:Number,color:uint,filled:Boolean,opacity:Number=1,side:Number=0):void {
            if(clamp(opacity)==0)return;
            // One magazine silhouette, explicit backing; sideways tips still travel only horizontally.
            var points:Array=[[0,-8],[3.5,-3],[3.5,7],[-3.5,7],[-3.5,-3],[0,-8],[-3.5,4],[3.5,4]];
            for(var pass:int=0;pass<2;pass++) {
                var ink:uint=pass?color:0x10181E;
                g.lineStyle(pass?1:3,ink,clamp(opacity),false,LineScaleMode.NORMAL,CapsStyle.ROUND,JointStyle.ROUND);
                if(filled)g.beginFill(ink,clamp(opacity));
                for(var i:int=0;i<(pass?8:6);i++) {
                    var px:Number=x+(side?side*points[i][1]:points[i][0]);
                    var py:Number=y+(side?-side*points[i][0]:points[i][1]);
                    if(i==0||i==6)g.moveTo(px,py);else g.lineTo(px,py);
                    if(i==5&&filled)g.endFill();
                }
            }
        }
        // Native type IDs are not menu order. Preserve the 14 slots and their opacity contract.
        private function center():void {
            if(data.arty) {
                var dot:uint=ready()?GREEN:RED;
                marks.graphics.lineStyle();
                marks.graphics.beginFill(0x10181E,1);marks.graphics.drawCircle(0,0,4);marks.graphics.endFill();
                marks.graphics.beginFill(dot,1);marks.graphics.drawCircle(0,0,3);marks.graphics.endFill();
                return;
            }
            var type:int=int(data.centerType),a:Number=clamp(data.centerOpacity);
            if(!isFinite(data.centerType)||type<0||type>13||a==0)return;
            var order:Array=[0,1,2,12,13,7,10,11,6,3,4,5,8,9];
            var slot:int=order.indexOf(type);
            var kind:String=["A","A","gap","gap","corners","corners","ring","ring","T","T","plus","plus","dot","dot"][slot];
            var color:uint=slot%2?CYAN:WHITE;
            var g:Graphics=marks.graphics;
            for(var pass:int=0;pass<2;pass++) {
                var ink:uint=pass?color:0x10181E;
                var width:Number=kind=="A"?2.5:kind=="ring"?1.25:2;
                g.lineStyle(width+(pass?0:2),ink,a,false,LineScaleMode.NORMAL,CapsStyle.ROUND,JointStyle.ROUND);
                if(kind=="A") {
                    // Approved large A geometry, now paired white / timer blue.
                    g.moveTo(-8.75,15);g.lineTo(0,0);g.lineTo(8.75,15);
                } else if(kind=="corners"||kind=="gap") {
                    var paths:Array=kind=="corners"?
                        [[[-6,-15],[-15,-15],[-15,-6]],[[6,-15],[15,-15],[15,-6]],[[15,6],[15,15],[6,15]],[[-6,15],[-15,15],[-15,6]]]:
                        [[[-15,0],[-7,0]],[[7,0],[15,0]],[[0,-15],[0,-7]],[[0,7],[0,15]]];
                    for(var i:int=0;i<paths.length;i++) {
                        g.moveTo(paths[i][0][0],paths[i][0][1]);
                        for(var j:int=1;j<paths[i].length;j++)g.lineTo(paths[i][j][0],paths[i][j][1]);
                    }
                } else if(kind=="ring")g.drawCircle(0,0,6.5);
                else {
                    if(kind=="T"||kind=="plus") {
                        if(pass)g.lineStyle();else g.lineStyle(2,ink,a,false,LineScaleMode.NORMAL,CapsStyle.ROUND,JointStyle.ROUND);
                        g.beginFill(ink,a);
                        // One silhouette prevents dark seams at the centre of the cross.
                        g.moveTo(-12,-1);
                        if(kind=="plus") {g.lineTo(-1,-1);g.lineTo(-1,-12);g.lineTo(1,-12);g.lineTo(1,-1);}
                        g.lineTo(12,-1);g.lineTo(12,1);g.lineTo(1,1);
                        g.lineTo(1,12);g.lineTo(-1,12);g.lineTo(-1,1);g.lineTo(-12,1);g.lineTo(-12,-1);
                    } else {
                        g.lineStyle();g.beginFill(ink,a);g.drawCircle(0,0,pass?3:4);
                    }
                    g.endFill();
                }
            }
            if(kind=="corners") {
                g.lineStyle();g.beginFill(0x10181E,a);g.drawCircle(0,0,2);g.endFill();
                g.beginFill(color,a);g.drawCircle(0,0,1);g.endFill();
            }
        }
        private function traverseMarks(values:Array):void {
            var g:Graphics=arrows.graphics;
            g.clear();
            if(!values.length)return;
            var left:Number=values[0], right:Number=values[1];
            var leftRatio:Number=values[2], rightRatio:Number=values[3];
            arrows.rotation=values[4];
            for(var pass:int=0;pass<2;pass++) {
                g.lineStyle(pass?2:4,pass?healthColor(leftRatio):0x10181E,1,false,LineScaleMode.NORMAL,CapsStyle.ROUND,JointStyle.ROUND);
                g.moveTo(left-8,-7);g.lineTo(left,0);g.lineTo(left-8,7);
                g.lineStyle(pass?2:4,pass?healthColor(rightRatio):0x10181E,1,false,LineScaleMode.NORMAL,CapsStyle.ROUND,JointStyle.ROUND);
                g.moveTo(right+8,-7);g.lineTo(right,0);g.lineTo(right+8,7);
            }
        }
        public function refresh():void {
            var dirty:Object=changed();
            if(dirty) {
                refreshText(dirty);
                if(dirty.arty || dirty.health || dirty.maxHealth || dirty.healthRatio || dirty.healthOpacity ||
                   dirty.reloadOpacity || dirty.centerType || dirty.centerOpacity || dirty.clipOpacity ||
                   dirty.distance || dirty.zoom || dirty.total || dirty.burstTime || dirty.capacity ||
                   dirty.burstSize || dirty.loaded || (data.arty && (dirty.reloadState || dirty.ammo))) {
                    refreshGraphics();
                }
            }
            var now:Number=getTimer();
            var left:Number=data.traverseLeft, right:Number=data.traverseRight;
            var lr:Number=data.traverseLeftRatio, rr:Number=data.traverseRightRatio;
            var rotation:Number=data.arty?data.traverseRotation:0;
            var valid:Boolean=isFinite(left)&&left<=0&&isFinite(right)&&right>=0&&isFinite(lr)&&isFinite(rr)&&isFinite(rotation);
            var values:Array=frame("traverse",valid?[left,right,lr,rr,rotation]:[],now,100,false,360);
            if(values)traverseMarks(values);

            var p:Number=reloadCharge();
            var scanning:Number=data.reloadState=="reloadingProgress"&&isFinite(data.progress)?1:0;
            var reload:Object=motion.reload;
            values=frame("reload",[p,scanning],now,90,!reload||!scanning||reload.target[1]!=scanning||p<reload.target[0]);
            var reloadOpacity:Number=clamp(data.reloadOpacity);
            if(values || (data.arty && drawnReloadOpacity!=reloadOpacity)) {
                drawnReloadOpacity=reloadOpacity;
                drawReload(values || motion.reload.value);
            }

            if(data.arty) {
                var rx:Number=data.splashRadiusX, ry:Number=data.splashRadiusY;
                var sx:Number=isFinite(data.splashX)?data.splashX:0;
                var sy:Number=isFinite(data.splashY)?data.splashY:0;
                var angle:Number=isFinite(data.splashRotation)?data.splashRotation:0;
                var splash:Number=data.splash>0?data.splash:0;
                var last:Object=motion.splash;
                values=frame("splash",isFinite(rx)&&isFinite(ry)&&rx>0&&ry>0?[rx,ry,sx,sy,splash,angle]:[],
                    now,100,last && last.target[4]!=splash,180);
                if(values)drawFootprint(values);
            }
        }
        private function drawReload(values:Array):void {
            var p:Number=values[0], g:Graphics=core.graphics;
            g.clear();
            if(data.arty) {
                if(p>0&&p<1)artyRail(g,-1,p,0x10181E,4.2,drawnReloadOpacity);
                artyRail(g,-1,p,CYAN,2.2,drawnReloadOpacity);
            } else if(values[1]) {
                // Reload uses only the horizontal section; HP still uses the folded rail.
                var x:Number=RAIL_OUTER-p*RAIL_HORIZONTAL;
                shell(g,-x,0,CYAN,true,1,-1);
                shell(g,x,0,CYAN,true,1,1);
            }
        }
        public function setAim(armor:Number,chance:Number,color:Number):void {
            if(data.arty)return;
            data.aimArmor=previous.aimArmor=armor;
            data.aimChance=previous.aimChance=chance;
            data.aimColor=previous.aimColor=color;
            refreshAim();
        }
        private function refreshAim():void {
            var chance:Number=data.aimChance;
            var show:Boolean=isFinite(data.aimArmor) && isFinite(data.aimColor) &&
                (chance==-1 || (chance>=0 && chance<=100));
            fields.aimArmor.visible=show;
            put("aimArmor",show?number(data.aimArmor,0," mm")+" / "+
                (chance==-1?"\u8df3\u5f39":chance.toFixed(0)+"%") : "");
            if(show) {
                fields.aimArmor.textColor=uint(data.aimColor);
                centerTextAt(fields.aimArmor,aimCenterY());
            }
        }
        private function centerTextAt(label:TextField,y:Number):void {
            label.y=y-2-label.textHeight/2;
        }
        private function refreshText(dirty:Object):void {
            var remaining:Boolean=dirty.remaining || dirty.reloadState || dirty.readyText || dirty.ammo;
            var total:Boolean=dirty.total || dirty.capacity || dirty.burstTime;
            var penetration:Boolean=dirty.shell || dirty.penetration;
            if(remaining)put("remaining",ready()?(data.readyText||"Ready"):number(data.remaining,2," s"));
            if(total) {
                var fullReload:String=number(data.total,2,"s");
                if(data.capacity>1)fullReload+="/"+number(data.burstTime,2,"s");
                put("total",fullReload);
            }
            if(dirty.health)put("health",number(data.health));
            if(dirty.health || dirty.maxHealth || dirty.healthRatio)fields.health.textColor=healthColor(hpRatio());
            if(dirty.distance)put("distance",data.distance);
            if(dirty.zoom)put("zoom",data.zoom);
            if(dirty.ammo)put("ammo",number(data.ammo));
            if(penetration)put("penetration",(data.shell?data.shell:"—")+" / "+number(data.penetration,0," mm"));
            if(dirty.timeOpacity)fields.remaining.alpha=fields.total.alpha=clamp(data.timeOpacity);
            if(dirty.healthOpacity)fields.health.alpha=clamp(data.healthOpacity);
            if(dirty.arty || dirty.height)put("height",data.arty?number(data.height,0," m"):"");
            if(dirty.arty || dirty.flight)put("flight",data.arty?number(data.flight,2," s"):"");
            if(dirty.arty || dirty.splash)put("splash",data.arty&&data.splash>0?number(data.splash,1," m"):"");
            if(data.arty) {
                if(dirty.arty || remaining || total)mirrorField(fields.remaining,fields.total);
                if(dirty.arty || dirty.health || penetration)mirrorField(fields.health,fields.penetration);
                if(dirty.arty || dirty.height || dirty.flight)mirrorField(fields.height,fields.flight);
                if(dirty.arty || dirty.distance || dirty.health || dirty.ammo)centerTextAt(fields.ammo,clipCenterY()+30);
            } else {
                if(dirty.aimArmor || dirty.aimChance || dirty.aimColor)refreshAim();
                else if(dirty.arty || dirty.distance || dirty.health)centerTextAt(fields.aimArmor,aimCenterY());
                if(dirty.arty || dirty.distance || dirty.health || dirty.zoom || total || dirty.ammo)
                    centerTextAt(fields.ammo,2*aimCenterY()-clipCenterY());
            }
        }
        private function refreshGraphics():void {
            var hp:Number=hpRatio();
            var healthOpacity:Number=clamp(data.healthOpacity), reloadOpacity:Number=clamp(data.reloadOpacity);
            charge.alpha=data.arty?1:healthOpacity*reloadOpacity;
            var nextRails:Array=data.arty?[hp,healthOpacity,reloadOpacity]:[hp,healthOpacity];
            if(!sameNumbers(railState,nextRails)) {
                railState=nextRails;
                drawRails(hp,healthOpacity,reloadOpacity);
            }

            var count:int=clipGroups();
            var loaded:int=isFinite(data.loaded)?Math.max(0,Math.floor(data.loaded/Math.max(1,data.burstSize))):0;
            var iconY:Number=clipCenterY()+.5; // outline spans -9.5 to +8.5 around the origin
            var clipOpacity:Number=clamp(data.clipOpacity);
            var nextMarks:Array=data.arty?[ready()?1:0]:[isFinite(data.centerType)?data.centerType:-1,clamp(data.centerOpacity)];
            if(count>0 && count<=10)nextMarks.push(count,loaded,iconY,clipOpacity);
            if(!sameNumbers(markState,nextMarks)) {
                markState=nextMarks;
                marks.graphics.clear();center();
                // ponytail: up to 10 groups use shell icons; larger magazines retain the native cassette.
                if(count<=10)for(var i:int=0;i<count;i++)shell(marks.graphics,(i-(count-1)/2)*15,iconY,CYAN,i<loaded,clipOpacity);
            }
        }
        private function drawRails(hp:Number,healthOpacity:Number,reloadOpacity:Number):void {
            var g:Graphics=rails.graphics, color:uint=healthColor(hp);
            g.clear();
            if(data.arty) {
                artyRail(g,-1,1,0x10181E,4.2,reloadOpacity);
                artyRail(g,-1,1,WHITE,2.2,reloadOpacity);
                artyRail(g,1,1,0x10181E,4.2,healthOpacity);
                artyRail(g,1,1,WHITE,2.2,healthOpacity);
                if(hp>0&&hp<1)artyRail(g,1,hp,0x10181E,4.2,healthOpacity);
                artyRail(g,1,hp,color,2.2,healthOpacity);
            } else {
                for(var side:int=-1;side<=1;side+=2) {
                    rail(g,side,0,1,0x10181E,4.2,healthOpacity);
                    rail(g,side,hp,1,0xFFFFFF,2.2,healthOpacity);
                    if(hp>0&&hp<1)rail(g,side,0,hp,0x10181E,4.2,healthOpacity);
                    rail(g,side,0,hp,color,2.2,healthOpacity);
                }
            }
        }
        private function drawFootprint(values:Array):void {
            footprint.graphics.clear();
            var sx:Number=values.length?values[2]:0, sy:Number=values.length?values[3]:0;
            var rotation:Number=values.length?values[5]:0;
            footprint.x=sx;footprint.y=sy;footprint.rotation=rotation;
            fields.splash.x=sx-fields.splash.width/2;fields.splash.y=sy+80;
            if(values.length) {
                var rx:Number=values[0], ry:Number=values[1];
                var angle:Number=rotation*Math.PI/180;
                var verticalX:Number=rx*Math.sin(angle),verticalY:Number=ry*Math.cos(angle);
                fields.splash.y=sy+Math.sqrt(verticalX*verticalX+verticalY*verticalY)+10;
                for(var pass:int=0;pass<2;pass++) {
                    footprint.graphics.lineStyle(pass?4:6,pass?ORANGE:0x10181E,1,false,LineScaleMode.NONE,CapsStyle.ROUND,JointStyle.ROUND);
                    footprint.graphics.drawEllipse(-rx,-ry,rx*2,ry*2);
                }
            }
        }
    }
}
