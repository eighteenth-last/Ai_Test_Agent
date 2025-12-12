const chrome = require('chrome-launcher');
const CDP = require('chrome-remote-interface');

(async () => {
    console.log('启动自动答题脚本...\n');
    
    const chromeProc = await chrome.launch({
        chromeFlags: ['--disable-gpu', '--no-sandbox']
    });
    
    console.log('Chrome debug port =', chromeProc.port);
    const client = await CDP({port: chromeProc.port});
    const {Page, Runtime} = client;

    await Page.enable();
    await Runtime.enable();

    // 打开目标页面
    const targetUrl = 'http://123.56.3.98:81/stu/#/pages/login/student';
    console.log('正在打开页面:', targetUrl);
    await Page.navigate({url: targetUrl});

    // 等待页面加载完成
    await Page.loadEventFired();
    console.log('页面加载完成\n');

    // 等待用户手动登录和进入答题页面
    console.log('请手动完成以下操作：');
    console.log('1. 登录账号');
    console.log('2. 进入答题页面');
    console.log('3. 等待题目加载完成');
    console.log('\n准备好后，在控制台输入任意字符并按回车开始答题...\n');
    
    // 等待用户输入确认
    await new Promise((resolve) => {
        process.stdin.once('data', () => {
            resolve();
        });
    });

    console.log('\n开始自动答题...\n');

    // 获取题目总数 - 使用更精确的检测
    const {result: totalResult} = await Runtime.evaluate({
        expression: `
        (function() {
            // 尝试多种方式检测题目
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
            
            console.log('检测到的元素数量:', count);
            return count;
        })();
        `,
        returnByValue: true
    });
    
    const total = totalResult.value || 0;
    
    if (total === 0) {
        console.log('❌ 未检测到题目！请确认：');
        console.log('1. 是否已进入答题页面？');
        console.log('2. 题目是否已加载完成？');
        console.log('\n脚本退出。');
        process.exit(0);
    }
    
    if (total > 100) {
        console.log(`❌ 检测到 ${total} 个元素，数量异常！可能不在答题页面。`);
        console.log('脚本退出。');
        process.exit(0);
    }
    
    console.log(`✓ 检测到 ${total} 道题目\n`);

    // 逐题作答
    for (let i = 0; i < total; i++) {
        console.log(`正在作答第 ${i + 1}/${total} 题...`);
        
        await Runtime.evaluate({
            expression: `
            (function() {
                try {
                    // 尝试多种选择器找到题目容器
                    const selectors = [
                        '.question-wrapper',
                        '.question-item',
                        '[class*="question"]',
                        '.topic-item'
                    ];
                    
                    let questions = [];
                    for (const sel of selectors) {
                        questions = document.querySelectorAll(sel);
                        if (questions.length > 0) break;
                    }
                    
                    if (questions.length === 0) {
                        console.log('未找到题目容器');
                        return;
                    }
                    
                    const q = questions[${i}];
                    if (!q) {
                        console.log('题目 ${i + 1} 不存在');
                        return;
                    }
                    
                    // 滚动到当前题目
                    q.scrollIntoView({block: 'center', behavior: 'smooth'});
                    q.style.border = '3px solid #ff0000';
                    q.style.backgroundColor = '#fff3cd';
                    
                    // 等待一下让页面稳定
                    setTimeout(() => {
                        // 1. 处理单选/多选（点击选项）
                        const options = q.querySelectorAll('.option-item, .el-radio, .el-checkbox, [class*="option"]');
                        if (options.length > 0) {
                            console.log('检测到选择题，选项数:', options.length);
                            // 点击第一个选项（单选）或所有选项（多选）
                            options[0]?.click();
                            return;
                        }
                        
                        // 2. 处理判断题（正确/错误）
                        const judgeOptions = q.querySelectorAll('label, button, [class*="judge"]');
                        for (const opt of judgeOptions) {
                            if (opt.textContent.includes('正确') || opt.textContent.includes('True')) {
                                opt.click();
                                console.log('检测到判断题，选择：正确');
                                return;
                            }
                        }
                        
                        // 3. 处理输入框（填空题/简答题）
                        const inputs = q.querySelectorAll('input[type="text"], textarea, .el-input__inner');
                        if (inputs.length > 0) {
                            console.log('检测到输入题，输入框数:', inputs.length);
                            inputs.forEach((input, idx) => {
                                input.value = '答案' + (idx + 1);
                                input.dispatchEvent(new Event('input', {bubbles: true}));
                                input.dispatchEvent(new Event('change', {bubbles: true}));
                            });
                            return;
                        }
                        
                        // 4. 处理下拉框
                        const selects = q.querySelectorAll('select, .el-select');
                        if (selects.length > 0) {
                            console.log('检测到下拉框');
                            selects.forEach(sel => {
                                if (sel.tagName === 'SELECT' && sel.options.length > 1) {
                                    sel.selectedIndex = 1;
                                    sel.dispatchEvent(new Event('change', {bubbles: true}));
                                } else {
                                    sel.click();
                                }
                            });
                            return;
                        }
                        
                        console.log('未识别题型，尝试点击第一个可点击元素');
                        const clickable = q.querySelector('label, button, input, .clickable');
                        if (clickable) clickable.click();
                        
                    }, 100);
                    
                } catch (error) {
                    console.error('作答出错:', error.message);
                }
            })();
            `,
            returnByValue: true
        });
        
        // 等待动画和请求完成
        await new Promise(r => setTimeout(r, 500));
        
        // 尝试点击"下一题"按钮
        await Runtime.evaluate({
            expression: `
            (function() {
                const nextBtnSelectors = [
                    '.next-btn',
                    '.btn-next',
                    'button:contains("下一题")',
                    '[class*="next"]',
                    '.el-button--primary'
                ];
                
                for (const sel of nextBtnSelectors) {
                    const btn = document.querySelector(sel);
                    if (btn && !btn.disabled && btn.textContent.includes('下一题')) {
                        btn.click();
                        console.log('点击下一题按钮');
                        break;
                    }
                }
            })();
            `,
            returnByValue: true
        });
        
        await new Promise(r => setTimeout(r, 300));
    }

    console.log('\n所有题目已作答完成！\n');

    // 尝试点击提交按钮
    console.log('尝试提交答案...');
    await Runtime.evaluate({
        expression: `
        (function() {
            const submitSelectors = [
                '.submit-btn',
                '.btn-submit',
                'button:contains("提交")',
                '[class*="submit"]',
                '.el-button--success'
            ];
            
            for (const sel of submitSelectors) {
                const btn = document.querySelector(sel);
                if (btn && !btn.disabled) {
                    const text = btn.textContent || btn.innerText;
                    if (text.includes('提交') || text.includes('完成')) {
                        console.log('找到提交按钮:', text);
                        btn.click();
                        return true;
                    }
                }
            }
            
            // 如果没找到，列出所有按钮
            const allButtons = document.querySelectorAll('button');
            console.log('页面所有按钮:', Array.from(allButtons).map(b => b.textContent).join(', '));
            return false;
        })();
        `,
        returnByValue: true
    });

    await new Promise(r => setTimeout(r, 1000));

    console.log('\n@@ALL_DONE@@');
    console.log('\n自动答题完成！');
    console.log('请手动检查答题结果，如需提交请在页面上点击提交按钮。');
    
    // 保持浏览器打开，不自动关闭
    console.log('\n浏览器将保持打开状态，按 Ctrl+C 退出脚本。');

})().catch(err => {
    console.error('脚本执行出错:', err);
    process.exit(1);
});
