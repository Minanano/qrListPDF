import React, { useEffect } from 'react';
import { fontBase64Map } from './fonts/fontBase64'; // 请根据实际路径调整

const DynamicFontLoader = () => {
  useEffect(() => {
    const styleElement = document.createElement('style');
    let cssRules = '';

    // 遍历所有字体
    Object.keys(fontBase64Map).forEach((fontKey) => {
      const fontInfo = fontBase64Map[fontKey];
      const family = fontInfo.family; // 注册使用的字体族名

      // 遍历该字体的所有权重（normal / bold）
      Object.keys(fontInfo.weights).forEach((weightKey) => {
        const weightInfo = fontInfo.weights[weightKey];
        const base64 = weightInfo.base64;
        const fontWeight = weightInfo.weight ; // bold → 700，normal → 400
        const fontStyle = 'normal'; // 当前所有字体均为 normal 风格

        cssRules += `
          @font-face {
            font-family: '${family}';
            src: url(data:font/truetype;base64,${base64}) format('truetype');
            font-weight: ${fontWeight};
            font-style: ${fontStyle};
          }
        `;
      });
    });

    // 注入 CSS
    styleElement.appendChild(document.createTextNode(cssRules));
    document.head.appendChild(styleElement);

    // 组件卸载时清理，防止内存泄漏
    return () => {
      if (document.head.contains(styleElement)) {
        document.head.removeChild(styleElement);
      }
    };
  }, []);

  // 该组件不渲染任何内容，仅负责加载字体
  return null;
};

export default DynamicFontLoader;