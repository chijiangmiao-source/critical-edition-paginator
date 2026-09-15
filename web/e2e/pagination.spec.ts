import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/')
})

test('编辑篇章结构：容量、段落增删改、保持标记、注记增删', async ({ page }) => {
  // 修改容量
  await page.getByTestId('capacity-input').fill('12')
  await expect(page.getByTestId('capacity-input')).toHaveValue('12')

  // 新增段落并编辑行数
  await page.getByTestId('add-paragraph').click()
  await expect(page.locator('[data-testid^="paragraph-row-"]')).toHaveCount(3)
  await page.getByTestId('lines-input-p3').fill('7')
  await expect(page.getByTestId('lines-input-p3')).toHaveValue('7')

  // 切换保持标记（末段复选框禁用：无下段可保持）
  await expect(page.getByTestId('keep-input-p3')).toBeDisabled()
  await page.getByTestId('keep-input-p1').uncheck()
  await expect(page.getByTestId('keep-input-p1')).not.toBeChecked()

  // 新增并删除注记
  await page.getByTestId('add-footnote').click()
  await expect(page.locator('[data-testid^="footnote-row-"]')).toHaveCount(3)
  await page.getByTestId('remove-footnote-n3').click()
  await expect(page.locator('[data-testid^="footnote-row-"]')).toHaveCount(2)

  // 删除段落
  await page.getByTestId('remove-paragraph-p3').click()
  await expect(page.locator('[data-testid^="paragraph-row-"]')).toHaveCount(2)

  // 段落改名后，注记下拉仍关联同一段落（按内部键而非 id 关联）
  await page.getByTestId('paragraph-id-k-p1').fill('p1x')
  await expect(
    page.getByTestId('footnote-paragraph-n1').locator('option:checked'),
  ).toHaveText('p1x')
})

test('成功预览：页卡片、容量算式、页下注与断点', async ({ page }) => {
  // 默认草稿：H=10，p1=5 行（保持），p2=6 行；n1 标记 p1 第 2 行高 2，n2 标记 p2 第 4 行高 3
  await page.getByTestId('compute-button').click()

  await expect(page.getByTestId('summary')).toContainText('共 2 页')
  const cards = page.getByTestId('page-card')
  await expect(cards).toHaveCount(2)

  // 第一页：第 1–7 行，注记 n1，容量算式与段内断点
  const first = cards.nth(0)
  await expect(first.locator('.page-header')).toHaveText('第 1 页（第 1–7 行）')
  await expect(first.getByTestId('page-line')).toHaveCount(7)
  await expect(first.getByTestId('page-footnote')).toHaveText(['n1（标记第 2 行，高 2）'])
  await expect(first.getByTestId('capacity-formula')).toHaveText(
    '正文 7 行 × 1 + 注记 2 = 9 / 容量 10（剩余 1）',
  )
  await expect(first.getByTestId('break-label')).toHaveText(
    '断点：段内断点（p2 第 2 行后，两侧均 ≥ 2 行）',
  )

  // 第二页：第 8–11 行，注记 n2，文档结束
  const second = cards.nth(1)
  await expect(second.getByTestId('page-footnote')).toHaveText(['n2（标记第 9 行，高 3）'])
  await expect(second.getByTestId('capacity-formula')).toHaveText(
    '正文 4 行 × 1 + 注记 3 = 7 / 容量 10（剩余 3）',
  )
  await expect(second.getByTestId('break-label')).toHaveText('断点：文档结束')
})

test('失败定位：最短不可行前缀末段高亮，注记列表不归责', async ({ page }) => {
  // 调整为不可行：H=3，p1=2 行且保持，p2=2 行；保留 n2 并改到 p2 第 1 行
  await page.getByTestId('capacity-input').fill('3')
  await page.getByTestId('lines-input-p1').fill('2')
  await page.getByTestId('lines-input-p2').fill('2')
  await page.getByTestId('remove-footnote-n1').click()
  await page.getByTestId('footnote-line-n2').fill('1')

  await page.getByTestId('compute-button').click()

  const panel = page.getByTestId('failure-panel')
  await expect(panel).toBeVisible()
  await expect(page.getByTestId('failure-paragraph')).toContainText('第 2 段「p2」')
  await expect(page.getByTestId('failure-paragraph')).toContainText('第 1–4 行')
  // 前缀内注记按标记行列出，且界面明确不作单独归责
  await expect(page.getByTestId('failure-footnotes')).toContainText('n2')
  await expect(panel).toContainText('不单独归责')
  // 编辑器中对应段落行被高亮
  await expect(page.getByTestId('paragraph-row-p2')).toHaveClass(/row-failure/)
  await expect(page.getByTestId('paragraph-row-p1')).not.toHaveClass(/row-failure/)
})

test('失败定位：前缀内无注记时返回空列表', async ({ page }) => {
  await page.getByTestId('capacity-input').fill('3')
  await page.getByTestId('lines-input-p1').fill('2')
  await page.getByTestId('lines-input-p2').fill('2')
  await page.getByTestId('remove-footnote-n1').click()
  await page.getByTestId('remove-footnote-n2').click()

  await page.getByTestId('compute-button').click()

  await expect(page.getByTestId('failure-panel')).toBeVisible()
  await expect(page.getByTestId('failure-paragraph')).toContainText('「p2」')
  await expect(page.getByTestId('failure-footnotes')).toHaveText('前缀范围内无注记')
})
