---
name: demo-auto-skill
description: A DEMO Agent Skill that should be executed full automatically
---

# demo-auto-skill

## 目标

本 Skill 旨在进行两个随机数的一系列运算并判定结果。

## 执行流程

1. 生成两个大于 0 且小于 x 的随机整数
2. 若生成的随机整数大于 y，则重复生成直至生成的两个整数都小于或等于 y
3. 比较生成的两个整数的大小（第一个数大于第二个数记为 `ge`，反之记为 `le`, 相等记为 `eq`）
4. 判断两个整数是否为偶数
5. 判断两个整数是否为质数
6. 判断两个整数的乘积是否为 3 的倍数
7. **严格输出以下形式的 JSON 对象**：
```json
{
  "x": int,
  "y": int,
  "numbers": [int: number1, int: number2],
  "comparison": string: enum("ge", "le", "eq"), 
  "parity": [string: number1_parity: enum("even", "odd"), string: number2_parity: enum("even", "odd")],
  "is_prime": [bool: number1_is_prime, bool: number2_is_prime],
  "is_3x": [bool: number1_is_3x, bool: number2_is_3x]，
  "generated_at": datetime: datetime.now()
}
```

## 注意事项

1. **本 Skill 执行过程中不得询问用户，所有决策需要 Agent 自己做出**
2. **本 Skill 的输出必须为单一 JSON 对象，严格符合输出形式的规定**
3. **本 Skill 的实现形式不限，既可直接由 Agent 的语义理解能力实现，也可以先编写代码后执行**