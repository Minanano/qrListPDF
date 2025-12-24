const { app, BrowserWindow, ipcMain, dialog } = require('electron')
const path = require('path')
const isDev = require('electron-is-dev')
const { Worker } = require('worker_threads')
const fs = require('fs')
const PDFDocument = require('pdfkit')

let mainWindow
let exportCancelled = false

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    }
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }
  // 新增：强制打开 DevTools（无论开发/打包，都打开）
  // mainWindow.webContents.openDevTools({ mode: 'detach' });  // 这行会弹出控制台窗口

  // // 新增：加载完成后显示窗口
  // mainWindow.once('ready-to-show', () => {
  //   mainWindow.show()
  // })

  // // 新增：如果加载失败，打印错误到控制台
  // mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
  //   console.error('加载失败:', errorDescription, validatedURL);
  // });
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

// Helper: choose output folder
async function askForOutputFolder() {
  const { filePaths } = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory', 'createDirectory']
  })
  if (!filePaths || !filePaths[0]) return null
  return filePaths[0]
}

// Main IPC handler for export
ipcMain.handle('export-start', async (event, payload) => {
  // payload: { codes: string[], mode: 'qr'|'barcode', options: {...}, perPdfPages }
  const outputDir = await askForOutputFolder()
  if (!outputDir) return { cancelled: true }

  exportCancelled = false

  try {
    await exportToPDFs(payload, outputDir, (progress) => {
      // progress: { type, pageIndex, totalPages, index }
      mainWindow.webContents.send('export-progress', progress)
    })
    mainWindow.webContents.send('export-finished', { ok: true, outputDir })
    return { ok: true }
  } catch (err) {
    console.error('Export error', err)
    mainWindow.webContents.send('export-finished', { ok: false, error: String(err) })
    return { ok: false, error: String(err) }
  }
})

ipcMain.on('export-cancel', () => {
  exportCancelled = true
})

// Export function: coordinates worker threads to generate images and assemble PDFs
async function exportToPDFs(payload, outputDir, onProgress) {
  const { codes, mode, options, perPdfPages = 50 } = payload
  // layout options
  const paper = options.paper || 'A4'
  const orientation = options.orientation || 'portrait'

  const paperMM = {
    A3: [420, 297], // mm -- note later we'll swap for orientation
    A4: [297, 210],
    A5: [210, 148],
  }[paper] || [297, 210]

  let [pw, ph] = paperMM
  if (orientation === 'portrait') {
    // currently we used swapped sizes in mapping above, so correct orientation
    // for simplicity, treat pw as width mm and ph as height mm
    ;[pw, ph] = paperMM
  } else {
    ;[pw, ph] = [paperMM[1], paperMM[0]]
  }

  // choose DPI for rendering - tradeoff between quality and memory
  const DPI = options.dpi || 150 // reasonable default
  const pxPerMm = DPI / 25.4
  const pageWidthPx = Math.round(pw * pxPerMm)
  const pageHeightPx = Math.round(ph * pxPerMm)

  // Layout calculation: compute how many per row/col given arrangement
  const arrangement = options.arrangement || 'horizontal' // 'horizontal'|'vertical'
  const perRow = options.perRow || 8
  const leftRightMarginPx = Math.round((options.sideMargin || 10) )
  const topBottomMarginPx = Math.round((options.topMargin || 10) )
  const spacingX = Math.round(options.spacingX || 10)
  const spacingY = Math.round(options.spacingY || 10)

  // compute item width
  let itemWidthPx = options.autoSize ? Math.floor((pageWidthPx / perRow) - (leftRightMarginPx*2)) : options.itemWidth || 200
  let itemHeightPx = options.itemHeight || itemWidthPx

  // build page slots (x,y positions in pixels) left->right, top->down
  const slots = []
  const cols = Math.floor(pageWidthPx / (itemWidthPx + leftRightMarginPx*2 + spacingX)) || perRow
  const rows = Math.floor(pageHeightPx / (itemHeightPx + topBottomMarginPx*2 + spacingY))
  const slotsPerPage = cols * rows

  if (slotsPerPage <= 0) throw new Error('单页容量为0，请检查尺寸/边距设置')

  // Function to create a PDFKit doc and write PNG images at coordinates
  function createPdfWriter(pdfIndex) {
    const outPath = path.join(outputDir, `qrbarcode_export_part_${pdfIndex + 1}.pdf`)
    const stream = fs.createWriteStream(outPath)
    const doc = new PDFDocument({ size: [pw * 2.8346456693, ph * 2.8346456693] }) // mm -> points
    doc.pipe(stream)
    return { doc, stream, outPath }
  }

  // Use worker threads to generate code images in parallel for a chunk of indices
  const numWorkers = Math.min(require('os').cpus().length, 6)
  const totalCodes = codes.length

  // Prepare pages grouping
  const totalPages = Math.ceil(totalCodes / slotsPerPage)
  const pdfsNeeded = Math.ceil(totalPages / perPdfPages)

  // we'll process page by page, ask workers to produce images for indices for that page, then write them to PDF
  let globalIndex = 0
  for (let pdfIndex = 0; pdfIndex < pdfsNeeded; pdfIndex++) {
    if (exportCancelled) throw new Error('Export cancelled by user')
    const { doc, stream, outPath } = createPdfWriter(pdfIndex)

    for (let pageInPdf = 0; pageInPdf < perPdfPages; pageInPdf++) {
      const pageNumber = pdfIndex * perPdfPages + pageInPdf
      if (pageNumber >= totalPages) break

      // compute indices for this page
      const startIdx = pageNumber * slotsPerPage
      const endIdx = Math.min(startIdx + slotsPerPage, totalCodes)
      const indices = []
      for (let i = startIdx; i < endIdx; i++) indices.push(i)

      // spawn workers in batches to generate buffers for indices
      // We'll partition indices evenly across workers
      const batchSize = Math.ceil(indices.length / numWorkers)
      const genPromises = []
      for (let w = 0; w < numWorkers; w++) {
        const chunk = indices.slice(w * batchSize, (w + 1) * batchSize)
        if (chunk.length === 0) continue
        genPromises.push(runWorker(chunk, codes, mode, options))
      }

      // gather buffers
      const resultsArray = await Promise.all(genPromises)
      // flatten
      const flattened = resultsArray.flat()

      // draw a page in PDF
      // PDFKit uses points with origin at top-left
      // Add new page for each page except first
      if (pageInPdf !== 0 || pdfIndex !== 0) doc.addPage()

      // compute columns and rows again with precise positions
      const colCount = cols
      const rowCount = rows

      for (let i = 0; i < flattened.length; i++) {
        const item = flattened[i]
        const idx = indices[i]
        // position
        const col = i % colCount
        const row = Math.floor(i / colCount)
        const xPx = col * (itemWidthPx + leftRightMarginPx*2 + spacingX) + leftRightMarginPx
        const yPx = row * (itemHeightPx + topBottomMarginPx*2 + spacingY) + topBottomMarginPx

        // convert px to PDF points (1 px @ DPI -> inches -> points)
        const xPt = xPx * (72 / DPI)
        const yPt = yPx * (72 / DPI)
        const wPt = itemWidthPx * (72 / DPI)
        const hPt = itemHeightPx * (72 / DPI)

        try {
          doc.image(item.buffer, xPt, yPt, { width: wPt, height: hPt })
        } catch (err) {
          console.warn('绘制图片出错 idx=', idx, err)
        }

        onProgress({ type: 'exporting', page: pageNumber + 1, pageTotal: totalPages, index: idx + 1, total: totalCodes })
        if (exportCancelled) throw new Error('Export cancelled by user')
      }

      // page done
    }

    // finalize pdf
    doc.end()
    await new Promise((resolve, reject) => {
      stream.on('finish', resolve)
      stream.on('error', reject)
    })

    onProgress({ type: 'pdf_done', pdfIndex: pdfIndex + 1, outPath })
  }
}

// helper: spawn worker thread and get generated images for assigned indices
function runWorker(indices, codes, mode, options) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(path.join(__dirname, 'worker.js'), {
      workerData: { indices, codes, mode, options }
    })

    const results = []
    worker.on('message', (msg) => {
      if (msg.type === 'progress') {
        mainWindow.webContents.send('export-progress', msg.data)
      } else if (msg.type === 'result') {
        // msg.items: [{ index, buffer }]
        for (const it of msg.items) {
          // Buffer was transferred as Uint8Array
          const buf = Buffer.from(it.buffer)
          results.push({ index: it.index, buffer: buf })
        }
      }
    })

    worker.on('error', (err) => reject(err))
    worker.on('exit', (code) => {
      if (code !== 0) {
        reject(new Error(`Worker stopped with exit code ${code}`))
      } else {
        // sort by index
        results.sort((a, b) => a.index - b.index)
        resolve(results)
      }
    })
  })
}