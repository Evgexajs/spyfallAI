import { Application } from 'pixi.js'

async function init() {
  const app = new Application()

  await app.init({
    width: 1920,
    height: 1080,
    backgroundColor: 0x000000,
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
  })

  const container = document.getElementById('app')
  if (container) {
    container.appendChild(app.canvas)
  }

  console.log('Spyfall Visualizer initialized')
}

init().catch(console.error)
