## 1. 页面布局与滚动容器改造

- [x] 1.1 重构 `server/assets/templates/ui/run_detail.html` 的主体布局为“文件区 + 对话区 + 错误区”三段式
- [x] 1.2 为文件树容器增加最大高度与 `overflow:auto`，确保长列表内滚动
- [x] 1.3 为文件预览容器增加最大高度与 `overflow:auto`，确保长文本内滚动

## 2. 对话区交互收敛

- [x] 2.1 将 stdout 区域调整为主对话窗口，并保留 SSE 增量渲染与自动滚动
- [x] 2.2 将 reply 输入区固定在主对话窗口下方，按 pending 状态启用/禁用提交
- [x] 2.3 保持 `pending/reply` 与 `status/end` 事件联动，确保 waiting_user 到 running/terminal 的 UI 状态正确收敛

## 3. stderr 独立展示

- [x] 3.1 将 stderr 从主对话区拆分为独立窗口并保持独立滚动
- [x] 3.2 保持 stderr 事件增量渲染逻辑，确保与 stdout 显示互不干扰

## 4. 文档与回归验证

- [x] 4.1 更新 `docs/api_reference.md` 中 Run 页面能力描述（对话区与 stderr 独立窗口）
- [x] 4.2 更新 `docs/dev_guide.md` 中 management UI Run 详情布局语义说明
- [x] 4.3 增补/更新 `tests/unit/test_ui_routes.py` 与 `tests/integration/test_ui_management_pages.py` 断言覆盖新布局与交互行为
