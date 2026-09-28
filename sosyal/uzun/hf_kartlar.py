import json, html
KART = {
 "k_oyun": ("01", "OYUNLAR", "4 oyun · Godot · tarayıcıda ücretsiz", "#FFB84D"),
 "k_web":  ("02", "WEB", "tarayıcıda çalışan 3 proje", "#7FD1FF"),
 "k_hari": ("03", "HARİTA", "yakınımda ne var?", "#C9A961"),
 "k_arac": ("04", "ARAÇLAR", "işin görünmeyen tarafı", "#9BE38A"),
}
BAS = """<!doctype html><html lang="tr"><head><meta charset="UTF-8"><script src="gsap.min.js"></script><style>
@font-face{font-family:Anton;src:url(Anton-Regular.ttf)}@font-face{font-family:Outfit;src:url(Outfit-Bold.ttf)}
@font-face{font-family:Mono;src:url(JetBrainsMono-Regular.ttf)}
html,body{margin:0;width:1080px;height:1920px;overflow:hidden;background:#0b0b0f}
#k{position:relative;width:1080px;height:1920px;overflow:hidden;background:radial-gradient(circle at 50% 42%,%GLOW%33 0,#0b0b0f 58%)}
.no{position:absolute;left:0;right:0;top:560px;text-align:center;font:400 330px Anton;color:transparent;-webkit-text-stroke:5px %RENK%;opacity:.9}
.bas{position:absolute;left:0;right:0;top:880px;text-align:center;font:400 190px Anton;color:#F4EBD8;letter-spacing:4px}
.bas span{display:inline-block}
.cizgi{position:absolute;left:190px;top:1110px;width:700px;height:10px;background:%RENK%;transform-origin:left center}
.alt{position:absolute;left:0;right:0;top:1160px;text-align:center;font:700 52px Outfit;color:#CFC6B4}
.sat{position:absolute;left:0;right:0;text-align:center;font:400 200px Anton;color:#F4EBD8}
</style></head><body><div id="k" data-composition-id="kart" data-width="1080" data-height="1920" data-start="0" data-duration="%SURE%">
%ICERIK%
<script>const tl=gsap.timeline({paused:true});%ANIM%window.__timelines=window.__timelines||{};window.__timelines["kart"]=tl;</script>
</div></body></html>"""
def kart(ad, no, bas, alt, renk, sure=2.2):
    harfler = "".join(f"<span>{html.escape(c) if c!=' ' else '&nbsp;'}</span>" for c in bas)
    ic = f'<div class="no">{no}</div><div class="bas">{harfler}</div><div class="cizgi"></div><div class="alt">{html.escape(alt)}</div>'
    an = ('tl.from(".no",{x:-700,opacity:0,duration:.45,ease:"power3.out"},0);'
          'tl.from(".bas span",{y:160,opacity:0,rotation:8,duration:.45,stagger:.045,ease:"back.out(2)"},.12);'
          'tl.from(".cizgi",{scaleX:0,duration:.4,ease:"power2.inOut"},.45);'
          'tl.from(".alt",{y:40,opacity:0,duration:.35,ease:"power2.out"},.6);'
          f'tl.to("#k",{{scale:1.06,duration:{sure},ease:"none"}},0);'
          f'tl.to("#k",{{opacity:0,duration:.18}},{sure-0.18});')
    return BAS.replace("%GLOW%", renk).replace("%RENK%", renk).replace("%SURE%", str(sure)).replace("%ICERIK%", ic).replace("%ANIM%", an)
def hook(sure=2.9):
    ic = ('<div class="sat" id="a" style="top:520px">28 PROJE</div>'
          '<div class="sat" id="b" style="top:760px;color:#C9A961">5.247 TEST</div>'
          '<div class="sat" id="c" style="top:1000px">TEK KİŞİ.</div>')
    an = ('tl.from("#a",{scale:2.4,opacity:0,duration:.28,ease:"power4.out"},0.05);'
          'tl.from("#b",{scale:2.4,opacity:0,duration:.28,ease:"power4.out"},0.75);'
          'tl.from("#c",{scale:2.4,opacity:0,duration:.28,ease:"power4.out"},1.45);'
          'tl.to("#k",{x:14,duration:.05,yoyo:true,repeat:3},1.45);'
          f'tl.to("#k",{{opacity:0,duration:.2}},{sure-0.2});')
    return BAS.replace("%GLOW%", "#C9A961").replace("%RENK%", "#C9A961").replace("%SURE%", str(sure)).replace("%ICERIK%", ic).replace("%ANIM%", an)
import os
for ad, v in KART.items():
    os.makedirs(ad, exist_ok=True); open(f"{ad}/index.html", "w").write(kart(ad, *v))
os.makedirs("hook", exist_ok=True); open("hook/index.html", "w").write(hook())
for d in list(KART) + ["hook"]:
    for f in ["gsap.min.js", "Anton-Regular.ttf", "Outfit-Bold.ttf", "JetBrainsMono-Regular.ttf"]:
        if not os.path.exists(f"{d}/{f}"): os.symlink(os.path.abspath(f), f"{d}/{f}")
    json.dump({"paths": {"blocks": "compositions", "assets": "assets"}}, open(f"{d}/hyperframes.json", "w"))
print("ok")
