const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');
(async () => {
  for (const name of ['sprout', 'history', 'book-heart', 'bell']) {
    const svg = fs.readFileSync(path.join(__dirname, '../node_modules/lucide-static/icons', name + '.svg'), 'utf8');
    for (const [suffix, color] of [['', '#66716a'], ['-active', '#246b4b']]) {
      await sharp(Buffer.from(svg.replaceAll('currentColor', color))).resize(64, 64).png()
        .toFile(path.join(__dirname, '../assets', name + suffix + '.png'));
    }
  }
})();
