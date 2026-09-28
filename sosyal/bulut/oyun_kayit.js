// Record real gameplay of a web (Godot HTML5) game in headless Chromium.
// WebGL runs on SwiftShader (CPU), so this works on machines without a GPU,
// e.g. the Higgsfield sandbox. Output: vid/*.webm (1280x720) + ekran-*.png.
//
// usage: NODE_PATH=$(npm root -g) node oyun_kayit.js <url> [saniye] [tuslar]
//   tuslar: comma list of "tus:basili_ms" pressed in a loop, default "Space:700"
//   First Enter presses skip the menu (most of our games start with Enter).
const { chromium } = require('playwright');
const [url, sn = '15', tuslar = 'Space:700'] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader',
    '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required'] });
  const c = await b.newContext({ viewport: { width: 1280, height: 720 },
    recordVideo: { dir: 'vid', size: { width: 1280, height: 720 } } });
  const p = await c.newPage();
  p.on('console', m => { if (m.type() === 'error') console.log('KONSOL', m.text().slice(0, 200)); });
  await p.goto(url, { waitUntil: 'load' });
  await p.waitForTimeout(9000);                 // Godot engine + pck download
  await p.screenshot({ path: 'ekran-menu.png' });
  await p.mouse.click(640, 360);                // user gesture: unlocks audio + focus
  for (let i = 0; i < 2; i++) { await p.keyboard.press('Enter'); await p.waitForTimeout(2500); }
  const plan = tuslar.split(',').map(s => s.split(':'));
  const bitis = Date.now() + Number(sn) * 1000;
  while (Date.now() < bitis) {
    for (const [tus, ms] of plan) {
      await p.keyboard.down(tus); await p.waitForTimeout(Number(ms));
      await p.keyboard.up(tus); await p.waitForTimeout(300);
    }
  }
  await p.screenshot({ path: 'ekran-oyun.png' });
  await c.close(); await b.close();
})();
