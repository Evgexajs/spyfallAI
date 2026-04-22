import { createApp } from '@render/index'

async function init() {
  await createApp()
  console.log('Spyfall Visualizer initialized')
}

init().catch(console.error)
