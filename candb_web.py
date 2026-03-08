import streamlit as st
import cantools
import os
import pandas as pd
import plotly.express as px

# 页面配置（适配手机端显示）
st.set_page_config(
    page_title="CANDB 查看工具",
    page_icon="📊",
    layout="wide",  # 宽屏布局，手机端自动适配
    initial_sidebar_state="collapsed"
)

# 自定义样式（优化手机端显示效果）
st.markdown("""
<style>
    .stExpander {
        margin-bottom: 10px;
    }
    .stFileUploader {
        padding: 10px 0;
    }
    @media (max-width: 768px) {
        h1 {
            font-size: 1.8rem !important;
        }
        h2 {
            font-size: 1.4rem !important;
        }
        h3 {
            font-size: 1.2rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# 标题和说明
st.title("📊 CANDB 查看工具")
st.caption("支持安卓/苹果/电脑访问 | 解析DBC文件 + 双向计算CAN信号")

# 分栏布局（适配手机）
col1, col2 = st.columns([2, 1])

with col1:
    # 1. 上传 DBC 文件
    uploaded_dbc = st.file_uploader("📁 选择 DBC 文件", type=["dbc", "txt"], key="dbc_upload")

with col2:
    st.markdown("#### 功能说明")
    st.write("✅ 解析DBC节点/消息/信号")
    st.write("✅ 正向：CAN数据 → 物理值/原始值")
    st.write("✅ 反向：物理值 → CAN数据")
    st.write("✅ 信号值可视化图表")

# 初始化 DBC 数据库
db = None
if uploaded_dbc is not None:
    # 保存临时 DBC 文件
    with open("temp.dbc", "wb") as f:
        f.write(uploaded_dbc.getbuffer())

    try:
        # 加载 DBC
        db = cantools.database.load_file("temp.dbc")
        st.success(f"✅ 成功加载 DBC 文件：{uploaded_dbc.name}")

        # 2. 显示 DBC 基础信息
        st.subheader("📋 DBC 基础信息")
        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.metric("节点数量", len(db.nodes))
        with info_col2:
            st.metric("消息数量", len(db.messages))

        # 3. 显示节点列表
        with st.expander("🔍 查看所有节点", expanded=False):
            st.write("节点列表：")
            for idx, node in enumerate(db.nodes, 1):
                st.write(f"{idx}. {node}")

        # 4. 显示消息和信号详情
        st.subheader("📡 消息与信号详情")
        # 消息筛选（方便手机端快速查找）
        msg_filter = st.text_input("搜索消息名称/ID", placeholder="输入关键词筛选...")

        for msg in db.messages:
            # 筛选逻辑
            if msg_filter and (msg_filter not in msg.name and msg_filter not in hex(msg.frame_id)):
                continue

            # 消息展开栏
            with st.expander(f"▶ 消息ID: 0x{msg.frame_id:X} | 名称: {msg.name}", expanded=False):
                msg_info_col1, msg_info_col2 = st.columns(2)
                with msg_info_col1:
                    st.write(f"长度：{msg.length} 字节")
                    # 修复：使用 getattr 安全访问 cycle_time
                    st.write(f"周期：{getattr(msg, 'cycle_time', '无')} ms")
                with msg_info_col2:
                    # 修复：使用 getattr 安全访问 sender
                    st.write(f"发送节点：{getattr(msg, 'sender', '无')}")
                    st.write(f"注释：{msg.comment if msg.comment else '无'}")

                # 信号列表
                st.write("### 信号详情")
                signal_data = []
                for sig in msg.signals:
                    signal_data.append({
                        "信号名称": sig.name,
                        "起始位": sig.start,
                        "长度(bit)": sig.length,
                        "系数(scale)": sig.scale,
                        "偏移(offset)": sig.offset,
                        "最小值": sig.minimum if sig.minimum else "无",
                        "最大值": sig.maximum if sig.maximum else "无",
                        "单位": sig.unit if sig.unit else "无"
                    })

                # 信号表格（适配手机横向滚动）
                st.dataframe(pd.DataFrame(signal_data), use_container_width=True)

        # 5. CAN 数据双向解析功能
        st.subheader("🧮 CAN 数据双向解析")
        with st.expander("展开使用解析功能", expanded=False):
            # 选择解析模式
            parse_mode = st.radio(
                "选择解析模式",
                ["正向解析：CAN数据 → 物理值", "反向生成：物理值 → CAN数据"],
                index=0
            )

            if parse_mode == "正向解析：CAN数据 → 物理值":
                # 正向解析逻辑（你现在用的）
                can_id = st.text_input("CAN ID (16进制，如 123 或 0x123)", placeholder="123")
                can_data = st.text_input("CAN 数据 (16进制，空格分隔，如 01 02 03)", placeholder="00 01 02 03")
                hex_type = st.radio("选择十六进制显示类型", ["物理值转十六进制", "原始值转十六进制"], index=1)

                if st.button("解析并显示十六进制"):
                    if not can_id or not can_data:
                        st.error("请输入 CAN ID 和 数据！")
                    else:
                        try:
                            can_id_int = int(can_id, 16) if can_id.startswith("0x") else int(can_id, 16)
                            can_data_bytes = bytes.fromhex(can_data.replace(" ", ""))

                            target_msg = None
                            for msg in db.messages:
                                if msg.frame_id == can_id_int:
                                    target_msg = msg
                                    break

                            if target_msg:
                                decoded_signals = db.decode_message(can_id_int, can_data_bytes)
                                st.success(f"解析成功！消息：{target_msg.name}")

                                st.write(f"### 信号物理值 + {hex_type}")
                                result_data = []
                                for sig_name, phys_value in decoded_signals.items():
                                    sig_obj = next(s for s in target_msg.signals if s.name == sig_name)
                                    
                                    if hex_type == "物理值转十六进制":
                                        int_phys = int(round(phys_value))
                                        hex_value = hex(int_phys)[2:].upper()
                                        hex_label = "物理值(十六进制)"
                                        hex_desc = f"0x{hex_value}"
                                    else:
                                        raw_value = int(round((phys_value - sig_obj.offset) / sig_obj.scale))
                                        hex_length = (sig_obj.length + 3) // 4
                                        hex_value = hex(raw_value)[2:].zfill(hex_length).upper()
                                        hex_label = "原始值(十六进制)"
                                        hex_desc = f"0x{hex_value}"
                                    
                                    result_data.append({
                                        "信号名称": sig_name,
                                        "物理值": round(phys_value, 4),
                                        "单位": sig_obj.unit if sig_obj.unit else "无",
                                        hex_label: hex_desc
                                    })
                                
                                st.dataframe(pd.DataFrame(result_data), use_container_width=True)

                                if result_data:
                                    st.write("### 信号值可视化")
                                    df_plot = pd.DataFrame(result_data)
                                    fig = px.bar(
                                        df_plot,
                                        x="信号名称",
                                        y="物理值",
                                        labels={"物理值": "物理值（带单位）"},
                                        title=f"消息 {target_msg.name} 信号值",
                                        template="plotly_white"
                                    )
                                    fig.update_layout(width=None, height=300, font=dict(size=10))
                                    st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.error(f"未找到 CAN ID: 0x{can_id_int:X} 对应的消息！")
                        except Exception as e:
                            st.error(f"解析失败：{str(e)}")

            else:
                # 反向生成逻辑（你要的：由物理值反推CAN数据）
                st.info("💡 选择消息后，输入信号物理值，自动生成对应的CAN原始数据")
                
                # 选择消息
                msg_options = [f"0x{m.frame_id:X} - {m.name}" for m in db.messages]
                selected_msg_str = st.selectbox("选择目标消息", msg_options)
                selected_msg = next(m for m in db.messages if f"0x{m.frame_id:X} - {m.name}" == selected_msg_str)

                # 输入信号物理值
                st.write("#### 输入信号物理值")
                signal_inputs = {}
                for sig in selected_msg.signals:
                    signal_inputs[sig.name] = st.number_input(
                        f"{sig.name} ({sig.unit if sig.unit else '无'})",
                        value=float(sig.minimum) if sig.minimum is not None else 0.0,
                        step=sig.scale
                    )

                if st.button("生成CAN原始数据"):
                    try:
                        # 计算原始值
                        raw_values = {}
                        for sig_name, phys_value in signal_inputs.items():
                            sig_obj = next(s for s in selected_msg.signals if s.name == sig_name)
                            raw_val = int(round((phys_value - sig_obj.offset) / sig_obj.scale))
                            raw_values[sig_name] = raw_val

                        # 编码为CAN数据
                        can_data_bytes = db.encode_message(selected_msg.frame_id, raw_values)
                        can_data_hex = " ".join([f"{b:02X}" for b in can_data_bytes])

                        st.success("✅ CAN原始数据生成成功！")
                        st.write("### 生成结果")
                        st.write(f"**消息ID**: 0x{selected_msg.frame_id:X} ({selected_msg.name})")
                        st.write(f"**CAN数据**: `{can_data_hex}`")

                        # 显示信号详情
                        st.write("#### 信号原始值详情")
                        result_data = []
                        for sig_name, raw_value in raw_values.items():
                            sig_obj = next(s for s in selected_msg.signals if s.name == sig_name)
                            hex_length = (sig_obj.length + 3) // 4
                            hex_value = hex(raw_value)[2:].zfill(hex_length).upper()
                            result_data.append({
                                "信号名称": sig_name,
                                "物理值": signal_inputs[sig_name],
                                "原始值(十进制)": raw_value,
                                "原始值(十六进制)": f"0x{hex_value}"
                            })
                        st.dataframe(pd.DataFrame(result_data), use_container_width=True)

                    except Exception as e:
                        st.error(f"生成失败：{str(e)}")

    except Exception as e:
        st.error(f"加载 DBC 文件失败：{str(e)}")
    finally:
        # 清理临时文件
        if os.path.exists("temp.dbc"):
            os.remove("temp.dbc")

# 底部说明（手机端可见）
st.markdown("---")
st.caption("💡 提示：手机端可左右滑动表格查看完整内容 | 所有数据仅本地解析，不会上传")
