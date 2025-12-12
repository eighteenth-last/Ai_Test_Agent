"""
自定义 Browser-Use Actions
为 Browser-Use 添加自动答题功能

作者: Ai_Test_Agent Team
版本: 1.0
"""

import asyncio
import logging
from browser_use.agent.views import ActionResult
from browser_use.browser.types import Page

logger = logging.getLogger(__name__)


async def auto_answer_questions(page: Page) -> ActionResult:
    """
    自动答题 Action
    检测页面上的题目并自动作答
    
    适用场景：
    - 单选题/多选题
    - 判断题
    - 填空题
    - 简答题
    
    Returns:
        ActionResult: 答题结果
    """
    try:
        logger.info('[AutoAnswer] 🎯 开始自动答题...')
        
        # 1. 获取题目总数
        total = await page.evaluate("""
            () => {
                let count = 0;
                
                // 方法1: 查找题目容器
                const wrappers = document.querySelectorAll('.question-wrapper, .topic-item, .question-item');
                if (wrappers.length > 0 && wrappers.length < 100) {
                    count = wrappers.length;
                }
                
                // 方法2: 查找题号
                if (count === 0) {
                    const numbers = document.querySelectorAll('[class*="question-number"], .topic-number');
                    if (numbers.length > 0 && numbers.length < 100) {
                        count = numbers.length;
                    }
                }
                
                // 方法3: 查找选项组
                if (count === 0) {
                    const optionGroups = document.querySelectorAll('.options, [class*="option-list"]');
                    if (optionGroups.length > 0 && optionGroups.length < 100) {
                        count = optionGroups.length;
                    }
                }
                
                return count;
            }
        """)
        
        if total == 0:
            msg = '[AutoAnswer] ❌ 未检测到题目'
            logger.warning(msg)
            return ActionResult(
                error=msg,
                include_in_memory=True,
                long_term_memory='未检测到题目'
            )
        
        if total > 100:
            msg = f'[AutoAnswer] ❌ 检测到 {total} 个元素，数量异常'
            logger.warning(msg)
            return ActionResult(
                error=msg,
                include_in_memory=True,
                long_term_memory='题目数量异常'
            )
        
        logger.info(f'[AutoAnswer] ✓ 检测到 {total} 道题目')
        
        # 2. 逐题作答
        for i in range(total):
            logger.info(f'[AutoAnswer] 正在作答第 {i + 1}/{total} 题...')
            
            # 执行答题逻辑
            await page.evaluate(f"""
                (index) => {{
                    try {{
                        const selectors = [
                            '.question-wrapper',
                            '.question-item',
                            '[class*="question"]',
                            '.topic-item'
                        ];
                        
                        let questions = [];
                        for (const sel of selectors) {{
                            questions = document.querySelectorAll(sel);
                            if (questions.length > 0) break;
                        }}
                        
                        if (questions.length === 0) return false;
                        
                        const q = questions[index];
                        if (!q) return false;
                        
                        // 滚动到当前题目
                        q.scrollIntoView({{block: 'center', behavior: 'smooth'}});
                        
                        setTimeout(() => {{
                            // 1. 处理单选/多选
                            const options = q.querySelectorAll('.option-item, .el-radio, .el-checkbox, [class*="option"]');
                            if (options.length > 0) {{
                                options[0]?.click();
                                return true;
                            }}
                            
                            // 2. 处理判断题
                            const judgeOptions = q.querySelectorAll('label, button, [class*="judge"]');
                            for (const opt of judgeOptions) {{
                                if (opt.textContent.includes('正确') || opt.textContent.includes('True')) {{
                                    opt.click();
                                    return true;
                                }}
                            }}
                            
                            // 3. 处理输入框
                            const inputs = q.querySelectorAll('input[type="text"], textarea, .el-input__inner');
                            if (inputs.length > 0) {{
                                inputs.forEach((input, idx) => {{
                                    input.value = '答案' + (idx + 1);
                                    input.dispatchEvent(new Event('input', {{bubbles: true}}));
                                    input.dispatchEvent(new Event('change', {{bubbles: true}}));
                                }});
                                return true;
                            }}
                            
                            // 4. 处理下拉框
                            const selects = q.querySelectorAll('select, .el-select');
                            if (selects.length > 0) {{
                                selects.forEach(sel => {{
                                    if (sel.tagName === 'SELECT' && sel.options.length > 1) {{
                                        sel.selectedIndex = 1;
                                        sel.dispatchEvent(new Event('change', {{bubbles: true}}));
                                    }} else {{
                                        sel.click();
                                    }}
                                }});
                                return true;
                            }}
                            
                            // 5. 尝试点击第一个可点击元素
                            const clickable = q.querySelector('label, button, input, .clickable');
                            if (clickable) {{
                                clickable.click();
                                return true;
                            }}
                            
                            return false;
                        }}, 100);
                        
                        return true;
                    }} catch (error) {{
                        console.error('作答出错:', error.message);
                        return false;
                    }}
                }}
            """, i)
            
            # 等待动画和请求完成
            await asyncio.sleep(0.5)
            
            # 尝试点击下一题按钮
            await page.evaluate("""
                () => {
                    const nextBtnSelectors = [
                        '.next-btn',
                        '.btn-next',
                        '[class*="next"]',
                        '.el-button--primary'
                    ];
                    
                    for (const sel of nextBtnSelectors) {
                        const btn = document.querySelector(sel);
                        if (btn && !btn.disabled && btn.textContent.includes('下一题')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            
            await asyncio.sleep(0.3)
        
        msg = f'[AutoAnswer] ✅ 所有题目已作答完成！共完成 {total} 道题'
        logger.info(msg)
        
        return ActionResult(
            extracted_content=msg,
            include_in_memory=True,
            long_term_memory=f'自动完成了 {total} 道题目的作答'
        )
    
    except Exception as e:
        msg = f'[AutoAnswer] ❌ 答题失败: {str(e)}'
        logger.error(msg)
        import traceback
        traceback.print_exc()
        
        return ActionResult(
            error=str(e),
            include_in_memory=True,
            long_term_memory='自动答题失败'
        )


def register_custom_actions(controller):
    """
    注册自定义 actions 到 controller
    
    Args:
        controller: Browser-Use 的 Controller 实例
    """
    @controller.registry.action(
        '自动答题 - 检测页面上的题目并自动作答（支持单选、多选、判断、填空等题型）',
    )
    async def auto_answer(page: Page):
        return await auto_answer_questions(page)
    
    logger.info('[CustomActions] ✓ 自定义答题 action 已注册')
