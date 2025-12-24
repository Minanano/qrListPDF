import React, { useState, useMemo, useEffect, useRef } from "react";
import {
  Layout,
  Select,
  Radio,
  Slider,
  Typography,
  Form,
  Input,
  Button,
  Space,
  Upload,
  message,
  Modal,
  Progress,
  Alert,
  Collapse,
  ColorPicker,
} from "antd";
import { UploadOutlined, FilePdfOutlined, CloseOutlined } from "@ant-design/icons";
import QRCodeStyling from "qr-code-styling";
import { jsPDF } from "jspdf";
import * as XLSX from 'xlsx';
import "antd/dist/reset.css";
import { PAPER_TYPE } from "./const";


const { Sider, Content } = Layout;
const { Title } = Typography;
const { Panel } = Collapse;

// 单位转换函数（保持不变）
const mmToPt = (mm) => Math.floor(mm * 2.83464566929);
const PRINT_DPI = 300;
const PREVIEW_DPI = 150;

// 获取当前时间字符串（保持不变）
const getCurrentTimeString = () => {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');
  const milliseconds = String(now.getMilliseconds()).padStart(3, '0');
  return `${year}${month}${day}_${hours}${minutes}${seconds}_${milliseconds}`;
};

const options = [
  { label: '纸张设置', value: 1 },
  { label: '二维码设置', value: 2 },
  { label: '文字设置', value: 3 },
];

// 可用的字体（jsPDF 支持的字体 + 常见中文字体）
const fontOptions = [
  { value: "helvetica", label: "Helvetica (英文默认)" },
  { value: "times", label: "Times New Roman" },
  { value: "courier", label: "Courier" },
  { value: "simsun", label: "宋体 (SimSun)" },
  { value: "simhei", label: "黑体 (SimHei)" },
  { value: "microsoftyahei", label: "微软雅黑 (Microsoft YaHei)" },
  { value: "kaiti", label: "楷体 (KaiTi)" },
  { value: "fangsong", label: "仿宋 (FangSong)" },
];

// 字重选项
const fontWeightOptions = [
  { value: 100, label: "100 (极细)" },
  { value: 200, label: "200" },
  { value: 300, label: "300 (细体)" },
  { value: 400, label: "400 (正常)" },
  { value: 500, label: "500" },
  { value: 600, label: "600" },
  { value: 700, label: "700 (粗体)" },
  { value: 800, label: "800" },
  { value: 900, label: "900 (黑体)" },
];

export default function App() {
  const qrItemRef = useRef(null);
  const [qrSize, setQrSize] = useState(20);
  const [qrColNum, setQrColNum] = useState(8);
  const [pageSize, setPageSize] = useState("A4");
  const [orientation, setOrientation] = useState("portrait");
  const [previewScale, setPreviewScale] = useState(85);
  const [fontSize, setFontSize] = useState(3);
  const [fontMargin, setFontMargin] = useState(0.5);
  const [paperMargin, setPaperMargin] = useState(6);
  const [qrPadding, setQrPadding] = useState(1.6);
  const[radioValue,setRadilValue]=useState(1);

  const [allData, setAllData] = useState([]);
  const [previewQRs, setPreviewQRs] = useState([]);
  const [exportModalVisible, setExportModalVisible] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);
  const [exportStatus, setExportStatus] = useState("");
  const [isExporting, setIsExporting] = useState(false);
  const [showConfirmClose, setShowConfirmClose] = useState(false);

  const abortExportRef = useRef(false);

  // 新增文字样式状态
  const [textFont, setTextFont] = useState("simsun");          // 字体
  const [textFontWeight, setTextFontWeight] = useState(400);   // 字重
  const [textColor, setTextColor] = useState("#000000");      // 文字颜色

  // 新增样式状态
  const [logoUrl, setLogoUrl] = useState(null); // logo 上传后 dataURL
  const [logoSize, setLogoSize] = useState(0.4); // 0.2 ~ 0.4 (对应 ~20%-40%，但库最大推荐0.4)
  const [logoMargin, setLogoMargin] = useState(0); // logo 与码点间距
  const [hideBackgroundDots, setHideBackgroundDots] = useState(true); // logo 区域隐藏码点（推荐）

  const [dotsColorType, setDotsColorType] = useState("solid"); // solid / gradient
  const [dotsSolidColor, setDotsSolidColor] = useState("#000000");
  const [dotsGradientType, setDotsGradientType] = useState("linear");
  const [dotsGradientRotation, setDotsGradientRotation] = useState(0);
  const [dotsStartColor, setDotsStartColor] = useState("#000000");
  const [dotsEndColor, setDotsEndColor] = useState("#000000");

  const [backgroundColor, setBackgroundColor] = useState("#FFFFFF");

  const [dotsStyle, setDotsStyle] = useState("square"); // square, rounded, dots, classy, classy-rounded, extra-rounded

  const [cornersSquareStyle, setCornersSquareStyle] = useState("square"); // square, dot, extra-rounded
  const [cornersSquareColor, setCornersSquareColor] = useState("#000000");

  const [cornersDotStyle, setCornersDotStyle] = useState("square");
  const [cornersDotColor, setCornersDotColor] = useState("#000000");

  // 布局计算（保持不变）
  const layout = useMemo(() => {
    const size = PAPER_TYPE[pageSize];
    const isPortrait = orientation === "portrait";
    const pageWidthMm = isPortrait ? size.width : size.height;
    const pageHeightMm = isPortrait ? size.height : size.width;
    const usableWidthMm = pageWidthMm - paperMargin * 2;
    const usableHeightMm = pageHeightMm - paperMargin * 2;
    const qrUnitWidthMm = qrSize + qrPadding * 2;
    const maxCols = Math.max(1, Math.floor(usableWidthMm / qrUnitWidthMm));
    let currentCols = qrColNum;
    if (currentCols > maxCols) currentCols = maxCols;
    const rowHeightMm = qrSize + fontSize + fontMargin + qrPadding * 2;
    const rows = Math.max(1, Math.floor(usableHeightMm / rowHeightMm));
    const perPage = currentCols * rows;

    return {
      pageWidthMm,
      pageHeightMm,
      usableWidthMm,
      usableHeightMm,
      qrWidthMm: qrSize,
      qrHeightMm: qrSize,
      qrColNum: currentCols,
      rows,
      perPage,
      maxCols,
      qrPixelPrint: Math.floor((qrSize / 25.4) * PRINT_DPI),
      qrPixelPreview: Math.floor((qrSize / 25.4) * PREVIEW_DPI),
    };
  }, [pageSize, orientation, qrSize, qrColNum, qrPadding, fontMargin, paperMargin, fontSize]);

  useEffect(() => {
    if (qrColNum > layout.maxCols) {
      setQrColNum(layout.maxCols);
    }
  }, [layout.maxCols, qrColNum]);

  const pages = useMemo(() => {
    const result = [];
    for (let i = 0; i < allData.length; i += layout.perPage) {
      result.push(allData.slice(i, i + layout.perPage));
    }
    return result;
  }, [allData, layout.perPage]);

  // 构建 qr-code-styling options
  const getQRCodeOptions = (pixelSize) => ({
    width: pixelSize,
    height: pixelSize,
    data: "https://example.com", // 临时，实际在生成时替换
    margin: 0,
    qrOptions: { errorCorrectionLevel: "H" },
    dotsOptions: {
      color: dotsColorType === "solid" ? dotsSolidColor : undefined,
      gradient: dotsColorType === "gradient" ? {
        type: dotsGradientType,
        rotation: dotsGradientRotation * Math.PI / 180,
        colorStops: [
          { offset: 0, color: dotsStartColor },
          { offset: 1, color: dotsEndColor }
        ]
      } : undefined,
      type: dotsStyle,
    },
    backgroundOptions: { color: backgroundColor },
    image: logoUrl || undefined,
    imageOptions: {
      crossOrigin: "anonymous",
      hideBackgroundDots,
      imageSize: logoSize,
      margin: logoMargin,
    },
    cornersSquareOptions: { type: cornersSquareStyle, color: cornersSquareColor },
    cornersDotOptions: { type: cornersDotStyle, color: cornersDotColor },
  });

  // 使用 qr-code-styling 生成 dataURL
  const generateStyledQR = async (text, pixelSize) => {
    const options = getQRCodeOptions(pixelSize);
    options.data = text;
    const qrCode = new QRCodeStyling(options);
    return await qrCode.getRawData("png").then(blob => URL.createObjectURL(blob));
  };

  const renderQr = async () => {
    const firstPage = pages[0] || [];
    if (firstPage.length === 0) return;

    message.loading({ content: "生成预览中...", key: "prev" });

    const qrs = await Promise.all(
      firstPage.map(async (item) => {
        const img = await generateStyledQR(item.qrContent, layout.qrPixelPreview);
        return { text: item.displayText, img, qrContent: item.qrContent };
      })
    );

    setPreviewQRs(qrs);
    message.success({ content: "预览已更新", key: "prev" });
  };

  useEffect(() => {
    if (allData.length > 0 && previewQRs.length > 0) {
      renderQr();
    }
  }, [
    logoUrl, logoSize, logoMargin, hideBackgroundDots,
    dotsColorType, dotsSolidColor, dotsGradientType, dotsGradientRotation, dotsStartColor, dotsEndColor,
    backgroundColor, dotsStyle, cornersSquareStyle, cornersSquareColor, cornersDotStyle, cornersDotColor,
    layout.qrPixelPreview,layout.perPage
  ]);

  const handlePreview = async () => {
    if (allData.length === 0) return message.warning("请先上传Excel文件");
    await renderQr();
  };

  // 导出 PDF（使用 qr-code-styling 生成高清）
  const handleExportPDF = async () => {
    if (allData.length === 0) return message.warning("没有数据");
    if (isExporting) return message.warning("正在导出中，请稍候");

    resetExportState();
    abortExportRef.current = false;

    setExportModalVisible(true);
    setExportProgress(0);
    setExportStatus("准备中...");
    setIsExporting(true);

    const pdf = new jsPDF({
      orientation: orientation === "portrait" ? "p" : "l",
      unit: "mm",
      // format: pageSize.toLowerCase(),
      format:[PAPER_TYPE[pageSize].width,PAPER_TYPE[pageSize].height]
    });
    // 转换颜色为 RGB
    const hexToRgb = (hex) => {
      const bigint = parseInt(hex.slice(1), 16);
      return [ (bigint >> 16) & 255, (bigint >> 8) & 255, bigint & 255 ];
    };
    const [r, g, b] = hexToRgb(textColor);

    const { qrWidthMm, qrHeightMm, qrColNum: currentCols, rows } = layout;
    let processedCount = 0;

    try {
      for (let p = 0; p < pages.length; p++) {
        if (abortExportRef.current) break;
        if (p > 0) pdf.addPage();

        const items = pages[p];

        for (let i = 0; i < items.length; i++) {
          if (abortExportRef.current) break;

          const row = Math.floor(i / currentCols);
          const col = i % currentCols;
          const x = paperMargin + qrPadding + col * (qrWidthMm + qrPadding * 2);
          const y = paperMargin + qrPadding + row * (qrHeightMm + fontSize + fontMargin  + qrPadding* 2);

          setExportStatus(`正在生成第${p + 1}页第${i + 1}个二维码`);

          const item = items[i];
          const img = await generateStyledQR(item.qrContent, layout.qrPixelPrint);

          processedCount++;
          pdf.addImage(img, "PNG", x, y, qrWidthMm, qrHeightMm);

          // 应用文字样式
          const effectiveFontWeight = textFontWeight >= 700 ? 'bold' : 'normal';  // 简化为 normal 或 bold
          pdf.setFont(textFont, effectiveFontWeight);  // 移除第三个参数，或传 'normal'
          // 如果是内置字体，直接用；自定义字体回退到 helvetica
          if (!['helvetica', 'times', 'courier'].includes(textFont)) {
            pdf.setFont('helvetica', effectiveFontWeight);  // 回退，避免警告
          }
          pdf.setFontSize(mmToPt(fontSize));
          pdf.setTextColor(textColor);
          pdf.text(
            item.displayText,
            x + qrWidthMm / 2,
            y + qrHeightMm + fontMargin + fontSize * 0.7,
            { align: "center", maxWidth: qrWidthMm }
          );

          await new Promise(resolve => setTimeout(resolve, 20));
          setExportProgress(Math.round((processedCount / allData.length) * 100));
        }
      }

      if (!abortExportRef.current && processedCount > 0) {
        setExportProgress(100);
        setExportStatus("导出完成！");
        setTimeout(() => {
          const timestamp = getCurrentTimeString();
          pdf.save(`批量二维码_${allData.length}个_${pageSize}_${orientation}_${timestamp}.pdf`);
          message.success("PDF 导出成功！");
          setTimeout(closeExportModal, 1000);
        }, 500);
      }
    } catch (err) {
      console.error(err);
      message.error("导出失败");
      setExportStatus("导出失败");
      setIsExporting(false);
    }
  };

  // Excel 上传（保持不变）
  const handleExcelUpload = (file) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target.result);
        const workbook = XLSX.read(data, { type: 'array' });
        const firstSheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheetName];
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
        const items = jsonData
          .filter(row => row && row.length >= 1)
          .map(row => {
            const qrContent = row[0] ? String(row[0]).trim() : '';
            const displayText = row[1] ? String(row[1]).trim() : qrContent;
            return qrContent ? { qrContent, displayText } : null;
          })
          .filter(item => item != null);

        if (items.length === 0) return message.warning("Excel文件中没有有效数据");
        setAllData(items);
        setPreviewQRs([]);
        message.success(`成功导入 ${items.length} 条数据`);
      } catch (error) {
        message.error('Excel文件解析失败');
      }
    };
    reader.readAsArrayBuffer(file);
    return false;
  };

  // Logo 上传
  const handleLogoUpload = (file ) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      setLogoUrl(e.target.result);
      message.success("Logo 上传成功");
    };
    reader.readAsDataURL(file);
    return false;
  };

  // 重置、停止、关闭等函数保持不变
  const resetExportState = () => {
    setExportProgress(0);
    setExportStatus("");
    setIsExporting(false);
    abortExportRef.current = false;
  };
  const stopExport = () => { abortExportRef.current = true; message.info("正在停止导出..."); };
  const handleCloseExportModal = () => { if (isExporting) setShowConfirmClose(true); else closeExportModal(); };
  const closeExportModal = () => { setExportModalVisible(false); setTimeout(resetExportState, 300); };
  const confirmAbortExport = () => { stopExport(); setShowConfirmClose(false); };
  const cancelAbortExport = () => setShowConfirmClose(false);

  return (
    <>
      <Layout style={{ height: "100vh" }}>
        <Sider width={560} style={{ background: "#fff", padding: 20, overflowY: "auto" }}>
          <Title level={4}>批量二维码生成器（高清打印）</Title>

          <Form layout="vertical">
            <Space>
              <Button type="primary" onClick={handlePreview} disabled={allData.length === 0}>
                预览第一页
              </Button>
              <Upload accept=".xlsx,.xls" beforeUpload={handleExcelUpload} showUploadList={false}>
                <Button icon={<UploadOutlined />}>上传Excel文件</Button>
              </Upload>
            </Space>

            {allData.length > 0 && (
              <div style={{ margin: "12px 0", color: "#666" }}>
                共 <strong>{allData.length}</strong> 条数据
                {pages.length > 1 && `，分为 ${pages.length} 页`}
              </div>
            )}

<Radio.Group
style={{marginTop:10,marginBottom:10}}
      block
      options={options}
      // defaultValue={1}
      value={radioValue}
      onChange={(e)=>setRadilValue(e.target.value)}
      optionType="button"
      buttonStyle="solid"
    />

            {radioValue==1?(<>
              <Form.Item label="纸张"><Select value={pageSize} onChange={setPageSize}>{Object.keys(PAPER_TYPE).map(key => (<Select.Option key={key} value={key}>{key}</Select.Option>))}</Select></Form.Item>
            <Form.Item label="方向"><Radio.Group value={orientation} onChange={e => setOrientation(e.target.value)}><Radio.Button value="portrait">纵向</Radio.Button><Radio.Button value="landscape">横向</Radio.Button></Radio.Group></Form.Item>
            <Form.Item label={`页边距 (${paperMargin}mm)`}><Slider min={0} max={50} value={paperMargin} onChange={setPaperMargin} /></Form.Item>
            </>):null}
            {radioValue==2?(<>
              
            <Collapse defaultActiveKey={"set"} accordion style={{marginBottom:10}}>
              <Panel header="码布局" key="set">
              <Form.Item label={`二维码尺寸 (${qrSize}mm)`}><Slider min={5} max={100} step={0.1} value={qrSize} onChange={setQrSize} /><div style={{ fontSize: 12, color: "#999", marginTop: 4 }}>当前设置下最大可放 {layout.maxCols} 列</div></Form.Item>
            <Form.Item label={`每行个数 (${qrColNum})`}><Slider min={1} max={layout.maxCols} value={qrColNum} onChange={setQrColNum} disabled={layout.maxCols <= 1} />{layout.maxCols <= 1 && <div style={{ fontSize: 12, color: "#ff4d4f", marginTop: 4 }}>二维码尺寸或页边距过大，无法放置二维码，请调整设置</div>}</Form.Item>
            <Form.Item label={`二维码间距 (${qrPadding}mm)`}><Slider step={0.1} min={0} max={20} value={qrPadding} onChange={setQrPadding} /></Form.Item>
                </Panel>
              <Panel header="Logo 设置" key="logo">
                <Form.Item label="上传 Logo">
                  <Upload beforeUpload={handleLogoUpload} showUploadList={false}><Button icon={<UploadOutlined />}>上传图片</Button></Upload>
                  {logoUrl && <Button onClick={() => setLogoUrl(null)} danger style={{ marginLeft: 8 }}>移除 Logo</Button>}
                </Form.Item>
                <Form.Item label={`Logo 尺寸 (${(logoSize * 100).toFixed(0)}%)`}><Slider min={0.1} max={0.4} step={0.01} value={logoSize} onChange={setLogoSize} /></Form.Item>
                <Form.Item label="Logo 间距"><Slider min={0} max={30} value={logoMargin} onChange={setLogoMargin} /></Form.Item>
                <Form.Item label="隐藏 Logo 背景点"><Radio.Group value={hideBackgroundDots} onChange={e => setHideBackgroundDots(e.target.value)}><Radio value={true}>是</Radio><Radio value={false}>否</Radio></Radio.Group></Form.Item>
              </Panel>

              <Panel header="码点与颜色" key="dots">
                <Form.Item label="码点颜色类型"><Radio.Group value={dotsColorType} onChange={e => setDotsColorType(e.target.value)}><Radio value="solid">纯色</Radio><Radio value="gradient">渐变色</Radio></Radio.Group></Form.Item>
                {dotsColorType === "solid" && <Form.Item label="码点颜色"><ColorPicker value={dotsSolidColor} onChange={(_, hex) => setDotsSolidColor(hex)} /></Form.Item>}
                {dotsColorType === "gradient" && (
                  <>
                    <Form.Item label="渐变类型"><Select value={dotsGradientType} onChange={setDotsGradientType}><Select.Option value="linear">线性</Select.Option><Select.Option value="radial">径向</Select.Option></Select></Form.Item>
                    {dotsGradientType==="linear" &&(
                      <Form.Item label="渐变旋转角度"><Slider min={0} max={360} value={dotsGradientRotation} onChange={setDotsGradientRotation} /></Form.Item>
                    )}
                    
                    <Form.Item label="起始颜色"><ColorPicker value={dotsStartColor} onChange={(_, hex) => setDotsStartColor(hex)} /></Form.Item>
                    <Form.Item label="结束颜色"><ColorPicker value={dotsEndColor} onChange={(_, hex) => setDotsEndColor(hex)} /></Form.Item>
                  </>
                )}
                <Form.Item label="码点形状"><Select value={dotsStyle} onChange={setDotsStyle}>
                  <Select.Option value="square">方形</Select.Option>
                  <Select.Option value="rounded">圆角</Select.Option>
                  <Select.Option value="extra-rounded">大圆角</Select.Option>
                  <Select.Option value="dots">小圆点</Select.Option>
                  <Select.Option value="classy">优雅</Select.Option>
                  <Select.Option value="classy-rounded">优雅圆角</Select.Option>
                </Select></Form.Item>
              </Panel>

              <Panel header="码眼设置" key="eyes">
                <Form.Item label="码外眼形状"><Select value={cornersSquareStyle} onChange={setCornersSquareStyle}>
                  <Select.Option value="square">方形</Select.Option>
                  <Select.Option value="dot">圆点</Select.Option>
                  <Select.Option value="rounded">圆角</Select.Option>
                  <Select.Option value="extra-rounded">大圆角</Select.Option>
                  <Select.Option value="dots">小圆点</Select.Option>
                  <Select.Option value="classy">优雅</Select.Option>
                  <Select.Option value="classy-rounded">优雅圆角</Select.Option>
                </Select></Form.Item>
                <Form.Item label="码外眼颜色"><ColorPicker value={cornersSquareColor} onChange={(_, hex) => setCornersSquareColor(hex)} /></Form.Item>
                <Form.Item label="码内眼形状"><Select value={cornersDotStyle} onChange={setCornersDotStyle}>
                <Select.Option value="square">方形</Select.Option>
                  <Select.Option value="dot">圆点</Select.Option>
                  <Select.Option value="rounded">圆角</Select.Option>
                  <Select.Option value="extra-rounded">大圆角</Select.Option>
                  <Select.Option value="dots">小圆点</Select.Option>
                  <Select.Option value="classy">优雅</Select.Option>
                  <Select.Option value="classy-rounded">优雅圆角</Select.Option>
                </Select></Form.Item>
                <Form.Item label="码内眼颜色"><ColorPicker value={cornersDotColor} onChange={(_, hex) => setCornersDotColor(hex)} /></Form.Item>
              </Panel>

              <Panel header="背景" key="bg">
                <Form.Item label="背景颜色"><ColorPicker value={backgroundColor} onChange={(_, hex) => setBackgroundColor(hex)} /></Form.Item>
              </Panel>
            </Collapse>
            </>):null}
            {radioValue==3?(<>
                <Form.Item label="字体">
                  <Select value={textFont} onChange={setTextFont}>
                    {fontOptions.map(f => (
                      <Select.Option key={f.value} value={f.value}>{f.label}</Select.Option>
                    ))}
                  </Select>
                </Form.Item>
                <Form.Item label="字重">
                  <Select value={textFontWeight} onChange={setTextFontWeight}>
                    {fontWeightOptions.map(w => (
                      <Select.Option key={w.value} value={w.value}>{w.label}</Select.Option>
                    ))}
                  </Select>
                </Form.Item>
                <Form.Item label="字体颜色">
                  <ColorPicker value={textColor} onChange={(_, hex) => setTextColor(hex)} />
                </Form.Item>
                <Form.Item label={`文字大小 (${fontSize}mm)`}>
                  <Slider step={0.1} min={0.1} max={15} value={fontSize} onChange={setFontSize} />
                </Form.Item>
                <Form.Item label={`文字间距 (${fontMargin}mm)`}>
                  <Slider step={0.1} min={0} max={15} value={fontMargin} onChange={setFontMargin} />
                </Form.Item>
              </>):null}
            
            
            
            <Form.Item label={"预览缩放: "+previewScale+"%"}><Slider min={30} max={100} value={previewScale} onChange={setPreviewScale} /></Form.Item>

            
            

            <Button type="primary" size="large" icon={<FilePdfOutlined />} block onClick={handleExportPDF} disabled={allData.length === 0 || isExporting} style={{ marginTop: 20 }} loading={isExporting}>
              {isExporting ? "正在导出..." : "导出全部为高清PDF"}
            </Button>
          </Form>
        </Sider>

        <Content style={{ background: "#f5f5f5", padding: 20, overflow: "auto" }}>
          <div style={{ textAlign: "center" }}>
            <div style={{
              display: "inline-block",
              background: "#fff",
              padding: `${paperMargin}mm`,
              boxShadow: "0 4px 20px rgba(0,0,0,0.15)",
              border: "1px solid #eee",
              transform: `scale(${previewScale / 100})`,
              transformOrigin: "top left",
              width: `${layout.pageWidthMm}mm`,
              height: `${layout.pageHeightMm}mm`,
              boxSizing: "border-box",
            }}>
              <div ref={qrItemRef}>
                {previewQRs.length === 0 ? (
                  <div style={{ color: "#aaa", paddingTop: 120, fontSize: 18 }}>
                    {allData.length === 0 ? "请上传Excel文件" : "点击预览第一页查看效果"}
                  </div>
                ) : (
                  <div style={{ position: "relative" }}>
                    {previewQRs.map((qr, i) => {
                      const row = Math.floor(i / layout.qrColNum);
                      const col = i % layout.qrColNum;
                      return (
                        <div key={i} style={{
                          position: "absolute",
                          left: `${  col * (layout.qrWidthMm + qrPadding * 2)}mm`,
                          top: `${ row * (layout.qrHeightMm + fontSize + fontMargin  + qrPadding* 2)}mm`,
                          width: `${layout.qrWidthMm}mm`,
                          padding:`${qrPadding}mm`,
                          textAlign: "center",
                          boxSizing: "unset"
                        }}>
                          <img src={qr.img} alt={qr.text} style={{ width: "100%", height: "100%", display: "block" }} />
                          
                          <div style={{
                            marginTop: `${fontMargin}mm`,
                            fontSize: `${fontSize}mm`,
                            fontFamily: textFont === "helvetica" ? "Helvetica" : 
                                         textFont === "times" ? "'Times New Roman'" :
                                         textFont === "courier" ? "Courier" :
                                         textFont === "simsun" ? "SimSun, serif" :
                                         textFont === "simhei" ? "SimHei, sans-serif" :
                                         textFont === "microsoftyahei" ? "Microsoft YaHei, sans-serif" :
                                         textFont === "kaiti" ? "KaiTi, serif" :
                                         textFont === "fangsong" ? "FangSong, serif" : "sans-serif",
                            fontWeight: textFontWeight,
                            color: textColor,
                            wordBreak: "break-all",
                            lineHeight: 1
                          }}>
                            {qr.text}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {pages.length > 1 && previewQRs.length > 0 && (
              <div style={{ marginTop: 20, color: "#888" }}>
                正在预览第 1 页，共 {pages.length} 页
              </div>
            )}
          </div>
        </Content>

        {/* 导出进度弹窗及确认中止弹窗保持不变 */}
        <Modal open={exportModalVisible} centered width={420} closable={!isExporting} onCancel={handleCloseExportModal}
          footer={isExporting ? [<Button key="stop" type="primary" danger onClick={() => setShowConfirmClose(true)}>终止导出</Button>] : null}
          maskClosable={!isExporting}>
          <div style={{ textAlign: "center", padding: "30px 20px" }}>
            <Title level={4}>{exportStatus}</Title>
            <Progress percent={exportProgress} status={exportProgress === 100 ? "success" : isExporting ? "active" : "normal"} strokeWidth={12} />
            {exportProgress === 100 && <div style={{ marginTop: 16, color: "#52c41a", fontSize: 16 }}>导出成功！</div>}
          </div>
        </Modal>

        <Modal open={showConfirmClose} centered width={400} closable={false} onCancel={cancelAbortExport}
          footer={[<Button key="cancel" onClick={cancelAbortExport}>取消</Button>,<Button key="confirm" type="primary" danger onClick={confirmAbortExport}>确认终止</Button>]}>
          <div style={{ padding: "20px", textAlign: "center" }}>
            <CloseOutlined style={{ fontSize: 48, color: "#ff4d4f", marginBottom: 16 }} />
            <Title level={4}>确认终止导出？</Title>
            <Alert message="导出过程正在进行中，确认终止将会中止当前导出任务，已导出的数据将不会保存。" type="error" />
          </div>
        </Modal>
      </Layout>
    </>
  );
}