// SPDX-License-Identifier: GPL-3.0-or-later
package {
    import flash.display.CapsStyle;
    import flash.display.Graphics;
    import flash.display.JointStyle;
    import flash.display.LineScaleMode;

    public final class SolidReticleArt {
        public static const WHITE:uint=0xF7FAFF, GREEN:uint=0x7FFF36;
        private static const BACK:uint=0x10181E;
        private static const RADIUS:Number=256;
        private static const TICKS:int=24;

        public static function ring(g:Graphics, progress:Number, solid:Boolean, bold:Boolean):void {
            g.clear();
            var ink:Number=bold?8:4;
            for (var pass:int=0;pass<2;pass++) {
                if (solid) {
                    if (!pass || progress<=0 || progress>=1) {
                        stroke(g,ink+(pass?0:2),pass?(progress>=1?GREEN:WHITE):BACK,LineScaleMode.NONE);
                        g.drawCircle(0,0,RADIUS);
                    } else {
                        stroke(g,ink,GREEN,LineScaleMode.NONE);
                        arc(g,0,progress);
                        stroke(g,ink,WHITE,LineScaleMode.NONE);
                        arc(g,progress,1);
                    }
                } else {
                    for (var i:int=0;i<TICKS;i++) {
                        var angle:Number=i*Math.PI*2/TICKS-Math.PI/2;
                        var x:Number=Math.cos(angle), y:Number=Math.sin(angle);
                        stroke(g,ink+(pass?0:2),pass?(i<progress*TICKS?GREEN:WHITE):BACK,LineScaleMode.NONE);
                        segment(g,x*206,y*206,x*RADIUS,y*RADIUS);
                    }
                }
            }
        }

        private static function arc(g:Graphics,from:Number,to:Number):void {
            var angle:Number=from*2*Math.PI-Math.PI/2;
            var steps:int=Math.ceil((to-from)*8);
            var step:Number=(to-from)*2*Math.PI/steps;
            var controlRadius:Number=RADIUS/Math.cos(step/2);
            g.moveTo(RADIUS*Math.cos(angle),RADIUS*Math.sin(angle));
            for (var i:int=0;i<steps;i++) {
                var middle:Number=angle+step/2;
                angle+=step;
                g.curveTo(controlRadius*Math.cos(middle),controlRadius*Math.sin(middle),
                    RADIUS*Math.cos(angle),RADIUS*Math.sin(angle));
            }
        }

        public static function gun(g:Graphics, type:Number, color:uint, blade:Boolean):void {
            g.clear();
            if (!isFinite(type)||type!=int(type)||type<0||type>=15) return;
            var group:int=int(type/3);
            if (blade) {
                // Match the user's diagonal indication without an imported gradient bitmap.
                stroke(g,2,color,LineScaleMode.NORMAL);
                for (var side:int=-1;side<=1;side+=2) {
                    segment(g,side*18,-18,side*34,-34);
                    segment(g,side*18,18,side*34,34);
                }
            }
            for (var pass:int=0;pass<2;pass++) {
                var ink:uint=pass?color:BACK;
                var width:Number=group==0?2.5:group==3?1.25:2;
                stroke(g,width+(pass?0:2),ink,LineScaleMode.NORMAL);
                if (group==0) {
                    g.moveTo(-8.75,15); g.lineTo(0,0); g.lineTo(8.75,15);
                } else if (group==1) {
                    if (pass) g.lineStyle();
                    else stroke(g,2,ink,LineScaleMode.NORMAL);
                    g.beginFill(ink);
                    g.moveTo(-12,-1);g.lineTo(-1,-1);g.lineTo(-1,-12);g.lineTo(1,-12);
                    g.lineTo(1,-1);g.lineTo(12,-1);g.lineTo(12,1);g.lineTo(1,1);
                    g.lineTo(1,12);g.lineTo(-1,12);g.lineTo(-1,1);g.lineTo(-12,1);g.lineTo(-12,-1);
                    g.endFill();
                } else if (group==2) {
                    dot(g,pass?3:4,ink);
                } else if (group==3) {
                    g.drawCircle(0,0,6.5);
                } else {
                    segment(g,-15,0,-7,0); segment(g,7,0,15,0);
                    segment(g,0,-15,0,-7); segment(g,0,7,0,15);
                }
            }
        }

        public static function point(g:Graphics, color:uint):void {
            g.clear();
            dot(g,5.5,BACK);
            dot(g,4,color);
        }

        private static function dot(g:Graphics, radius:Number, color:uint):void {
            g.lineStyle();g.beginFill(color);g.drawCircle(0,0,radius);g.endFill();
        }

        private static function stroke(g:Graphics,width:Number,color:uint,scale:String):void {
            g.lineStyle(width,color,1,false,scale,CapsStyle.ROUND,JointStyle.ROUND);
        }

        private static function segment(g:Graphics,x0:Number,y0:Number,x1:Number,y1:Number):void {
            g.moveTo(x0,y0);g.lineTo(x1,y1);
        }
    }
}
