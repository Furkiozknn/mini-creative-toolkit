import asyncio, subprocess, time, os, shutil
from playwright.async_api import async_playwright
SITELER = [("nova", "/home/claude/nova-drift", 8801), ("masal", "/home/claude/masal", 8802), ("ajanlar", "/home/claude/turkce-ajanlar/web", 8803)]
async def kaydet(p, ad, port, adimlar):
    b = await p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    c = await b.new_context(viewport={"width": 540, "height": 960}, device_scale_factor=1, is_mobile=False, locale="tr-TR",
                            record_video_dir=f"v_{ad}", record_video_size={"width": 540, "height": 960})
    pg = await c.new_page()
    pg.on("console", lambda m: m.type == "error" and print(ad, "KONSOL", m.text[:160]))
    await pg.goto(f"http://127.0.0.1:{port}/", wait_until="load")
    await adimlar(pg)
    await c.close(); await b.close()
async def nova(pg):
    await pg.wait_for_timeout(2500)
    await pg.keyboard.press("Space")
    for i in range(14):
        k = "ArrowLeft" if i % 3 != 1 else "ArrowRight"
        await pg.keyboard.down(k); await pg.wait_for_timeout(450); await pg.keyboard.up(k); await pg.wait_for_timeout(250)
async def masal(pg):
    await pg.wait_for_timeout(1500)
    await pg.click("#ad"); await pg.keyboard.type("Elif", delay=140)
    await pg.select_option("#yas", index=2)
    await pg.click("#sehir"); await pg.keyboard.type("Sinop", delay=140)
    await pg.wait_for_timeout(500); await pg.click("#olustur"); await pg.wait_for_timeout(3000)
    for _ in range(2):
        try:
            await pg.click("#ileri", timeout=1500); await pg.wait_for_timeout(2500)
        except Exception:
            await pg.mouse.wheel(0, 500); await pg.wait_for_timeout(1500)
async def ajanlar(pg):
    await pg.wait_for_timeout(1500)
    await pg.keyboard.press("/"); await pg.keyboard.type("oyun", delay=180); await pg.wait_for_timeout(1800)
    await pg.keyboard.press("Control+A"); await pg.keyboard.type("güvenlik", delay=160); await pg.wait_for_timeout(1800)
    await pg.mouse.wheel(0, 600); await pg.wait_for_timeout(1500)
async def main():
    sunucular = [subprocess.Popen(["python3", "-m", "http.server", str(port), "-b", "127.0.0.1"], cwd=kok,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for _, kok, port in SITELER]
    time.sleep(1.5)
    try:
        async with async_playwright() as p:
            for (ad, _, port), f in zip(SITELER, [nova, masal, ajanlar]):
                await kaydet(p, ad, port, f)
    finally:
        for s in sunucular: s.terminate()
asyncio.run(main())
