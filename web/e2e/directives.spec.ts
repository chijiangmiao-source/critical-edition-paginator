import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/')
})

/** 归约为 H=4、单段 6 行、无注记（无指令最优结束行 (3,6)）。 */
async function reduceToSingleParagraph(page) {
  await page.getByTestId('capacity-input').fill('4')
  await page.getByTestId('lines-input-p1').fill('6')
  await page.getByTestId('remove-paragraph-p2').click()
  await page.getByTestId('remove-footnote-n1').click()
  await page.getByTestId('remove-footnote-n2').click()
}

test('锁定断点参与重算，页卡片标注锁定', async ({ page }) => {
  await reduceToSingleParagraph(page)
  await page.getByTestId('compute-button').click()
  await expect(page.getByTestId('summary')).toContainText('[3, 6]')

  // 锁定第 3 行后（恰好是原最优断点）：解不变，第一页出现锁定标注
  await page.getByTestId('add-directive').click()
  await page.getByTestId('directive-line-0').fill('3')
  await page.getByTestId('compute-button').click()
  await expect(page.getByTestId('summary')).toContainText('[3, 6]')
  await expect(page.getByTestId('directive-status')).toContainText('有效指令 1 条')
  await expect(page.getByTestId('locked-badge')).toHaveCount(1)
  await expect(page.locator('[data-testid="page-card"]').first()).toContainText('锁定断点')

  // 改锁第 2 行后：整篇重算为 (2,6)，而非把锁定当装饰
  await page.getByTestId('directive-line-0').fill('2')
  await page.getByTestId('compute-button').click()
  await expect(page.getByTestId('summary')).toContainText('[2, 6]')
  const cards = page.getByTestId('page-card')
  await expect(cards.first().locator('.page-header')).toContainText('第 1–2 行')
  await expect(cards.first()).toContainText('人工锁定，必须保留')
})

test('禁止断开改变可行断点', async ({ page }) => {
  await reduceToSingleParagraph(page)
  await page.getByTestId('add-directive').click()
  await page.getByTestId('directive-kind-0').selectOption('no_split')
  await page.getByTestId('directive-line-0').fill('3')
  await page.getByTestId('compute-button').click()
  // 第 3 行后被禁，最优从 (3,6) 变为 (2,6)
  await expect(page.getByTestId('summary')).toContainText('[2, 6]')
})

test('指令冲突：给出唯一最小释放建议，一次确认后重算', async ({ page }) => {
  await reduceToSingleParagraph(page)
  await page.getByTestId('add-directive').click()
  await page.getByTestId('add-directive').click()
  await page.getByTestId('directive-line-0').fill('2')
  await page.getByTestId('directive-line-1').fill('3')
  await page.getByTestId('compute-button').click()

  const panel = page.getByTestId('release-panel')
  await expect(panel).toBeVisible()
  await expect(panel).toContainText('释放数量最少')
  // 释放序号最小的 #1（录入序号 0）
  await expect(page.getByTestId('release-item-0')).toContainText('#1')
  await expect(page.getByTestId('release-item-0')).toContainText('必须保留')
  // 建议预览已按既有目标可复算：保留锁第 3 行 ⇒ (3,6)
  await expect(page.getByTestId('summary')).toContainText('[3, 6]')

  // 一次确认释放并重算：面板消失，状态转为「已确认释放」
  await page.getByTestId('release-confirm').click()
  await expect(panel).toBeHidden()
  await expect(page.getByTestId('directive-status')).toContainText('已确认释放 1 条')
  await expect(page.getByTestId('summary')).toContainText('[3, 6]')
})

test('非法位置的指令就地标失效，其余编辑照常出预览', async ({ page }) => {
  await page.getByTestId('capacity-input').fill('10')
  await page.getByTestId('lines-input-p1').fill('3')
  await page.getByTestId('remove-paragraph-p2').click()
  await page.getByTestId('remove-footnote-n1').click()
  await page.getByTestId('remove-footnote-n2').click()

  // 3 行段锁定第 1 行后：首片段仅 1 行，位置非法
  await page.getByTestId('add-directive').click()
  await page.getByTestId('directive-line-0').fill('1')
  await page.getByTestId('compute-button').click()

  await expect(page.getByTestId('directive-invalid-0')).toBeVisible()
  await expect(page.getByTestId('directive-invalid-0')).toContainText('已失效')
  await expect(page.getByTestId('directive-status')).toContainText('失效 1 条')
  // 文档仍正常出预览（单页 1–3）
  await expect(page.locator('[data-testid="page-card"]')).toHaveCount(1)
})

test('目标段落被删除：指令按段落失配标失效并保留', async ({ page }) => {
  await page.getByTestId('capacity-input').fill('10')
  await page.getByTestId('add-paragraph').click() // p3
  await page.getByTestId('add-directive').click() // 默认指向 p1
  await page.getByTestId('directive-paragraph-0').selectOption({ label: 'p3' })
  await page.getByTestId('directive-line-0').fill('2')
  await page.getByTestId('remove-paragraph-p3').click()
  await page.getByTestId('compute-button').click()

  await expect(page.getByTestId('directive-invalid-0')).toContainText('已失配')
  // 指令行仍保留在编辑器中（下拉显示已删除段落的原 id）
  await expect(page.getByTestId('directive-paragraph-0')).toContainText('p3（已失配）')
  await expect(page.locator('[data-testid="directive-row-0"]')).toBeVisible()
})

test('段界禁止断开：原本在段界的分页被移走', async ({ page }) => {
  // H=6，p1、p2 各 4 行无注记：段界分页 (4,8) 平方和 8 最优。
  await page.getByTestId('capacity-input').fill('6')
  await page.getByTestId('keep-input-p1').uncheck()
  await page.getByTestId('lines-input-p1').fill('4')
  await page.getByTestId('lines-input-p2').fill('4')
  await page.getByTestId('remove-footnote-n1').click()
  await page.getByTestId('remove-footnote-n2').click()
  await page.getByTestId('compute-button').click()
  await expect(page.getByTestId('summary')).toContainText('[4, 8]')

  // 在 p1 段界（第 4 行后）禁止断开：不得断在段界；(2,8) 与 (6,8) 并列，取字典序 (2,8)
  await page.getByTestId('add-directive').click()
  await page.getByTestId('directive-kind-0').selectOption('no_split')
  await page.getByTestId('directive-line-0').fill('4')
  await page.getByTestId('compute-button').click()
  await expect(page.getByTestId('summary')).toContainText('[2, 8]')
  await expect(page.getByTestId('directive-status')).toContainText('有效指令 1 条')
  await expect(page.locator('[data-testid="directive-invalid-0"]')).toHaveCount(0)
})

test('段落改名后，原锁定指令不迁移、按段落 ID 失配标失效', async ({ page }) => {
  await page.getByTestId('capacity-input').fill('10')
  // 对 p1 第 5 行（段界）加锁定
  await page.getByTestId('add-directive').click()
  await page.getByTestId('directive-line-0').fill('5')
  await page.getByTestId('compute-button').click()
  await expect(page.locator('[data-testid="directive-invalid-0"]')).toHaveCount(0)

  // 段落 p1 改名为 p1x：指令仍持旧 id p1，重算后就地标失效，不作用到 p1x
  await page.getByTestId('paragraph-id-k-p1').fill('p1x')
  await page.getByTestId('compute-button').click()
  await expect(page.getByTestId('directive-invalid-0')).toBeVisible()
  await expect(page.getByTestId('directive-invalid-0')).toContainText('段落 ID 已失配')
  await expect(page.getByTestId('directive-status')).toContainText('失效 1 条')
  // 下拉中旧 id 以「已失配」形式保留，未被静默改绑到 p1x
  await expect(page.getByTestId('directive-paragraph-0')).toContainText('p1（已失配）')
})

test('原文档本身无解时显示最短不可行前缀，不混入指令归因', async ({ page }) => {
  // 与既有失败用例相同的不可行文档：H=3，p1=2 保持，p2=2；仅保留 n2 改到 p2 第 1 行
  await page.getByTestId('capacity-input').fill('3')
  await page.getByTestId('lines-input-p1').fill('2')
  await page.getByTestId('lines-input-p2').fill('2')
  await page.getByTestId('remove-footnote-n1').click()
  await page.getByTestId('footnote-line-n2').fill('1')

  // 附加一条合法的段界锁定指令
  await page.getByTestId('add-directive').click()
  await page.getByTestId('directive-line-0').fill('2')
  await page.getByTestId('compute-button').click()

  await expect(page.getByTestId('failure-panel')).toBeVisible()
  await expect(page.getByTestId('failure-paragraph')).toContainText('「p2」')
  await expect(page.getByTestId('failure-directive-note')).toContainText('与版式指令无关')
  // 不出现释放建议面板
  await expect(page.getByTestId('release-panel')).toHaveCount(0)
})
