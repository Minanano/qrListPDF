const { parentPort, workerData } = require('worker_threads')
const QRCode = require('qrcode')
const bwipjs = require('bwip-js')

async function generateQRBuffer(text, size, color, bg) {
  const opts = {
    type: 'png',
    width: size,
    margin: 0,
    color: {
      dark: color || '#000000',
      light: bg || '#FFFFFF'
    }
  }
  return await QRCode.toBuffer(String(text), opts)
}

async function generateBarcodeBuffer(text, bcid, width, height, color, bg) {
  // bwip-js options
  const opts = {
    bcid: bcid || 'code128',
    text: String(text),
    scale: Math.max(1, Math.round(width / 2)),
    height: Math.max(10, Math.round(height / 2)),
    includetext: false,
    backgroundcolor: (bg || '#FFFFFF').replace('#',''),
    paddingwidth: 0,
    paddingheight: 0,
  }
  return await bwipjs.toBuffer(opts)
}

;(async () => {
  try {
    const { indices, codes, mode, options } = workerData
    const items = []
    for (let idx of indices) {
      const text = codes[idx]
      if (mode === 'qr') {
        const size = options.itemWidth || 200
        const buf = await generateQRBuffer(text, size, options.qrColor || '#000000', options.backgroundColor || '#FFFFFF')
        // transfer as ArrayBuffer
        items.push({ index: idx, buffer: Uint8Array.from(buf).buffer })
      } else {
        const bcid = options.barcodeType || 'code128'
        const width = options.barWidth || 2
        const height = options.barHeight || 100
        const buf = await generateBarcodeBuffer(text, bcid, width, height, options.barColor || '#000000', options.backgroundColor || '#FFFFFF')
        items.push({ index: idx, buffer: Uint8Array.from(buf).buffer })
      }
      parentPort.postMessage({ type: 'progress', data: { idx } })
    }
    parentPort.postMessage({ type: 'result', items })
    process.exit(0)
  } catch (err) {
    parentPort.postMessage({ type: 'error', error: String(err) })
    process.exit(1)
  }
})()
