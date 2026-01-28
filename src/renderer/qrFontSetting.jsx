import React, { useState, useMemo, useEffect, useRef } from "react";
import {
    Select,
    Form,
    Input,
    ColorPicker,
} from "antd";
import { fontBase64Map } from "./fonts/fontBase64";





// 字重选项
const fontWeightOptions = [
    { value: "normal", label: "normal" },
    { value: "bold", label: "bold" },
];


const QrFontSetting = ({ id,                       // 每个实例的唯一标识
    onChange,
    dataColNumber,//数据一共多少列
}) => {
    const [textFont, setTextFont] = useState("simhei");          // 字体
    const [textFontWeight, setTextFontWeight] = useState("normal");   // 字重
    const [textColor, setTextColor] = useState("#000000");      // 文字颜色
    const [fontSize, setFontSize] = useState(3);
    const [fontMargin, setFontMargin] = useState(0.5)
    const [coustomTextLabel, setCoustomTextLabel] = useState("");
    const [dataTextIndex, setDataTextIndex] = useState(0);//文字显示第几列

    const fontOptions = useMemo(() => {
        return Object.keys(fontBase64Map).map(key => ({
            value: key,
            label: fontBase64Map[key].label,
        }));
    }, []);
    
    // 根据当前字体动态计算可用字重
    const availableWeights = useMemo(() => {
        const weights = fontBase64Map[textFont]?.weights || {};
        return Object.keys(weights).map(weightKey => {
            const weight = weights[weightKey].weight;
            return {
                value: weight,
                label: weight === "bold" ? "加粗" : "常规",
            };
        });
    }, [textFont]);
    useEffect(() => {
        const hasCurrentWeight = availableWeights.some(opt => opt.value === textFontWeight);
        if (!hasCurrentWeight && availableWeights.length > 0) {
            setTextFontWeight("normal"); // 所有字体至少有 normal
        }
    }, [textFont, availableWeights, textFontWeight]);

    // 每次变化都通知父组件
    const notifyChange = () => {
        onChange?.(id, {
            textFont,
            textFontWeight,
            textColor,
            fontSize,
            fontMargin,
            dataTextIndex,
            coustomTextLabel
        });
    };


    // 每个 setter 都触发通知
    useEffect(() => {
        notifyChange();
    }, [textFont, textFontWeight, textColor, fontSize, fontMargin, dataTextIndex, coustomTextLabel]);

    return (
        <>
        <Form layout="inline" style={{marginBottom:10}}>
            <Form.Item label="码下方字段">
                <Input value={coustomTextLabel} onChange={(e) => setCoustomTextLabel(e.target.value + "")} />
            </Form.Item>
            <Form.Item >
                <Select value={dataTextIndex} onChange={setDataTextIndex}>
                    {Array.from({ length: dataColNumber }, (_, index) => index).map(value => {
                        return <Select.Option key={value} value={value}>第{value + 1}列</Select.Option>
                    })}
                </Select>
            </Form.Item>
            </Form>
            <Form layout="inline" style={{marginBottom:10}}>
            <Form.Item label="字体">
                <Select value={textFont} onChange={setTextFont}>
                        {fontOptions.map(f => (
                            <Select.Option key={f.value} value={f.value}>
                                {f.label}
                            </Select.Option>
                        ))}
                    </Select>
            </Form.Item>
            <Form.Item label="字重">
                <Select value={textFontWeight} onChange={setTextFontWeight}>
                        {availableWeights.map(w => (
                            <Select.Option key={w.value} value={w.value}>
                                {w.label}
                            </Select.Option>
                        ))}
                    </Select>
            </Form.Item>

            <Form.Item label="字体大小">
                <Select value={fontSize} onChange={setFontSize} placeholder="字体大小">
                    {Array.from({ length: 30 }, (_, index) => {
                        const value = 0.5 + index * 0.5;  // 0.5, 1.0, 1.5, ..., 15.0
                        return (
                            <Select.Option key={value} value={value}>
                                {value.toFixed(1)} mm
                            </Select.Option>
                        );
                    })}
                </Select>

            </Form.Item>
            </Form>
            <Form layout="inline" style={{marginBottom:10}}>
            <Form.Item label="字体间距">
                <Select value={fontMargin} onChange={setFontMargin} placeholder="字体间距">
                    {Array.from({ length: 151 }, (_, index) => {
                        const value = 0 + index * 0.1;  // 0.5, 1.0, 1.5, ..., 15.0
                        return (
                            <Select.Option key={value} value={value}>
                                {value.toFixed(1)} mm
                            </Select.Option>
                        );
                    })}
                </Select>

            </Form.Item>
            <Form.Item label="字体颜色">
                <ColorPicker value={textColor} onChange={(_, hex) => setTextColor(hex)} placeholder="字体颜色" />
            </Form.Item>
        </Form>
        </>
    )
}

export default QrFontSetting;