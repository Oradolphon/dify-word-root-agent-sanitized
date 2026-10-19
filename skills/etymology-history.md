---
name: etymology-history
description: 查询并讲解英语单词的词源历史（源流脉络）。含 getEtymology 两种返回格式（Wiktionary 模板 / etymonline 散文）的解码规则、模板语法对照表、语言代码中文对照、缺失词的样板文字陷阱识别、变形词还原、中文源流输出模板与质量自检。当用户问"某个词的词源/来源/词源历史/为什么是这个意思"时使用。
---

# 词源历史查询工作流

## 何时使用
- "comprehend 的词源历史""retrospect 这个词是怎么来的""window 的源头是什么"。
- "为什么 inspect 有检查的意思"（想听来源，不是要入库）。

## 与「添加新单词」的区别
- 用户**只问词源** → 走本流程，**不要自动入库**；讲完源流可以顺口问一句"要不要入库"。
- 用户**报新词要入库** → 走 word-root-assistant 的入库流程，但解码词源的规则可以直接复用本流程。

## 标准步骤
1. **还原词典形**：用户给的若是变形，先还原成词典形（comprehends → comprehend；studies → study；running → run；geese → goose）。`getEtymology` 不认变形词，传变形会拿到"未收录样板"（见第 3 步）。
2. **调用**：`getEtymology(word="comprehend")`。
3. **判真伪**（最关键的一步）：
   - **Wiktionary 正常返回**：正文含 `{{...}}` 模板 → 按下面「模板解码表」解读。
   - **etymonline 正常返回**：英文散文、含年代（如 "1680s, ..."）→ 翻译并压缩成中文时间线。
   - **`cet_db` 返回**（CET 词库）：模板正文，与 wiktionary 同一套写法，但**多带几个字段**：`ipa`（可能为 `null`）、`level`（如 `CET4`）、`pie_root`。正文常有提取残留，先剥再解码：
     · 开头的 `1=== `（章节残留）与结尾孤立的 ` =`；
     · `{{wikidata lexeme|L477}}`（维基数据条目号，纯元数据）；
     · `Displaced {{noncog|enm|forleten|...}}`（被这个新词取代掉的旧词）——最多一句带过，通常直接舍去。
     `ipa` 有值就附音标，是 `null` 就不标（绝不自己拼读音标）。
   - **⚠️ 只有 `{{ety|...|tree=1}}` 骨架**：如 `architectural` 返回
     `{{ety|en|:af|architecture|-al<id:adjectival>|text=+|tree=1}}` —— 这是「派生自某词」的词源树目录，**不含任何语源内容**，按「一律丢弃」删掉就什么都不剩了。处理：把 `:af` 后面的**基词**（architecture）拿去重查一次，用基词的词源来讲，并说明本词是「基词 + 后缀（-al / -ion / -ly）」的派生形式（构词说明，不占词源层）。
   - **⚠️ 未收录陷阱**：`source` 为 `etymonline`，且正文就是这句网站简介 ——
     `The online etymology dictionary (etymonline) is the internet's go-to source for quick and reliable accounts of the origin and history of English words, phrases, and idioms.`
     → 这表示**根本没查到**，不是词源内容。处理：a) 换词典形再查一次；b) 仍失败就如实说"词源库未收录该词"，可补充你自己的词源判断，但必须标注"这是我的判断，不是词典收录"。
   - **⚠️ 直接 404 也是「未收录」**：工具可能连正文都不给，直接抛错 ——
     `tool invoke error: Request failed with status code 404 and {"error":"未找到 geocentricism 的词源信息"}`
     404 表示**当前查询未找到可用词源段落**，不能推出词不存在或所有词典均未收录；503/超时另按来源暂不可用处理。处理：a) 换词典形或同形异体重试一次（geocentricism → geocentrism → geocentric）；b) 仍 404 就如实说"词源库未收录该词"，用词根知识补拆解并标注"这是我的判断，不是词典收录"；c) **404 时没有 `ipa` 字段，音标一律不标**；d) 不要因为查不到词源就跳过词根分析，也不要跳过用户要求的入库。
   - **⚠️ 整词借入/无词源数据的词**：即使 404，也可以按构词讲（前缀 + 词根 + 后缀），但要说清"这是构词分析，不是词典记载的词源"。
4. **解码成源流**：把模板串还原成「语言 → 词形 → 含义」的链条。
5. **落到词根**：指出该词含哪些**规范词根**（对照 `roots-glossary.md`），让词源和词根家族打通。
6. **可选联动**：`findWord(word=...)` 查是否已入库；未入库可以问用户要不要 `addWord`。
7. **输出**：按下面「输出模板」给中文源流脉络。

## 模板解码表（Wiktionary）

### 语源关系类
| 模板 | 含义 | 渲染成中文 |
| --- | --- | --- |
| `{{inh\|en\|enm\|wyndowe}}` | 继承（inherent） | ← 中古英语 wyndowe |
| `{{der\|en\|la\|comprehendere\|t=to grasp}}` | 派生（derived） | ← 派生自拉丁语 comprehendere（"to grasp"） |
| `{{bor\|en\|fr\|télévision}}` / `{{bor+\|en\|fr\|antibiotique}}` | 借入（borrowed） | ← 借自法语 télévision |
| `{{m\|la\|com-\|t=with}}` | 提及某词 | 拉丁语 com-（"with"） |
| `{{m\|en\|eyethurl\|\|window, pupil}}` | 空位参数＝释义 | 释义在第 3 位，一样当 `t=` 处理 |
| `{{l\|en\|word}}` / `{{lang\|la\|x}}` | 语言内链接 | 取词形，丢掉模板 |
| `{{cog\|sco\|windae}}` | 同源词 | 同源：低地苏格兰语 windae |
| `{{ncog\|ang\|ēagþȳrel\|lit=eye hole}}` | 非同源参照 | 参照：古英语 ēagþȳrel（字面"eye hole"） |
| `{{doublet\|en\|comprend}}` | 同源双式词 | 同源双式词：comprend |
| `{{root\|en\|ine-pro\|*speḱ-}}` | 印欧词根 | 可追溯到原始印欧语词根 \*speḱ- |
| `{{w\|Marko Marulić}}` | 维基人名/条目链接 | 直接写名字，不写成 wiki 链接 |
| `{{etydate\|1570s}}` | 首见年代 | 首见于 1570 年代 |

### 构词分析类
| 模板 | 含义 | 渲染 |
| --- | --- | --- |
| `{{com\|en\|wind\|eye}}` / `{{compound\|...}}` | 复合词 | wind + eye |
| `{{af\|en\|in-\|credible}}` / `{{affix}}` | 派生构词 | in- + credible |
| `{{pre\|...}}` / `{{prefix\|...}}` | 前缀构词 | 前缀 x + |
| `{{suf\|...}}` / `{{suffix\|...}}` | 后缀构词 | + 后缀 x |
| `{{confix\|en\|retro\|spect}}` / `{{con\|en\|mono\|arch}}` | 前后缀式构词（con 是 confix 的别名） | retro + spect（当构词说明句写，不占词源层） |
| `{{surf\|en\|anti-\|-biotic}}` | 表面分析（surface analysis） | 表面构词：anti- + -biotic |
| `{{blend\|...}}` | 混成词 | 混成：a + b |
| `{{clipping\|...}}` | 截短 | 截短自 ... |
| `{{back-formation\|...}}` | 逆构词 | 逆构自 ... |
| `{{abbrev\|...}}` / `{{initialism\|...}}` | 缩写 | 缩写自 ... |

> 「Equivalent to {{suffix|en|isolate|ion}}」「Equivalent to {{prefix|...|...}}」这类句子只是**构词说明**，不是语源层：写成一句「构词上＝isolate + -ion」并入正文，或直接略去，**不要单列成一层词源**。

### 注释类
| 模板 | 渲染 |
| --- | --- |
| `{{gloss\|...}}` / `{{q\|...}}` / `{{qualifier\|...}}` | （...）括号注释 |
| `{{non-gloss definition\|...}}` | ...（直接写内容） |
| `{{lb\|en\|...}}` / `{{label\|en\|...}}` | ［...］标签 |
| `{{sense\|...}}` | ...（义项提示） |
| `{{glossary\|noun}}` / `{{glossary\|verb}}` / `{{glossary\|etymon}}` 等 | 斜体/术语标注（`{{gloss}}` 的别名，值任意） | 按词性写「名词」「动词」等；`etymon`（词源形）这类术语直接略去，不输出模板 |
| `{{sense 2}}` / `(sense 2)` 之类的义项索引 | 正文交叉引用 | 整段丢弃 |
| `{{t=\|...}}` `{{lit=\|...}}` `{{gloss=\|...}}` `{{pos=\|...}}` | 取等号后的内容当释义/字面义 |

### 一律丢弃（元数据/引用）
`<ref>...</ref>`、`{{cite-book|...}}`、`{{cite-web|...}}`、`{{R:...}}`、`{{rfv-etym|en}}`、`{{ety|...}}`、`{{etymon|...}}`（词源树目录）、以及这些命名参数：`nocat=1`、`tree=1`、`id=...`、`nocap=1`、`noent=1`、`text=1`、`lang=...`、`sc=...`。
`cet_db` 正文还要额外丢掉：`{{wikidata lexeme|L477}}`、开头的 `1=== `、结尾的 ` =`、`{{noncog|...}}`（被取代的旧词，必要时一句话带过）。
→ 只取语源链，不把模板或文献引用丢给用户。

另有几类**版式噪音**，同样整段丢弃，不要当成词源内容：
- `thumb|...` / `thumbnail|...` 开头的图片说明行（如 `thumb|People in masquerade at the [[Carnival of Venice]] in 2015`）。
- 双中括号内链 `[[Venice, Italy, in 2015]]`、`[[mask]]`：整段丢弃或只保留必要的纯文字。
- `{{w|条目名}}` 之外的其他维基导航模板（导航框、分类、条目链接堆）。
- 词源段落里的维基百科式导语（"The {{glossary|noun}} is borrowed from..." 里那层英文语法外壳），只取里面的语源链。

## 语言代码 → 中文
| 代码 | 语言 | 代码 | 语言 |
| --- | --- | --- | --- |
| en | 英语 | la | 拉丁语 |
| enm | 中古英语 | la-med | 中世纪拉丁语 |
| ang | 古英语 | la-ren | 文艺复兴拉丁语 |
| sco | 低地苏格兰语 | la-lat | 晚期拉丁语 |
| non | 古诺斯语 | la-new | 新拉丁语 |
| is | 冰岛语 | grc | 古希腊语 |
| da | 丹麦语 | gkm | 中古希腊语 |
| sv | 瑞典语 | el | 现代希腊语 |
| nb / nn | 书面/新挪威语 | ine-pro | 原始印欧语 |
| fo | 法罗语 | itc-pro | 原始意大利语 |
| ovd | 厄尔夫达尔语 | gem-pro | 原始日耳曼语 |
| de | 德语 | cel-pro | 原始凯尔特语 |
| goh / gmh | 古/中古高地德语 | sla-pro | 原始斯拉夫语 |
| gsw / bar | 阿勒曼尼/巴伐利亚德语 | sem-pro | 原始闪米特语 |
| nl | 荷兰语 | ar | 阿拉伯语 |
| yi | 意第绪语 | he | 希伯来语 |
| fr | 法语 | fa | 波斯语 |
| frm / fro | 中古/古法语 | peo | 古波斯语 |
| xno | 盎格鲁-诺曼语 | ae | 阿维斯陀语 |
| nrf | 诺曼语 | sa | 梵语 |
| pro / oc | 古普罗旺斯语/奥克语 | pi | 巴利语 |
| ca | 加泰罗尼亚语 | zh | 汉语 |
| es | 西班牙语 | ja | 日语 |
| it | 意大利语 | ko | 朝鲜语 |
| pt | 葡萄牙语 | vi | 越南语 |
| scn / nap / vec | 西西里/那不勒斯/威尼斯语 | th | 泰语 |
| ro | 罗马尼亚语 | ms | 马来语 |
| ru | 俄语 | tcy | 图卢语（Tulu） |
| pl | 波兰语 | ta | 泰米尔语 |
| cs | 捷克语 | tr | 土耳其语 |
| uk | 乌克兰语 | hy | 亚美尼亚语 |
| lt / lv | 立陶宛语/拉脱维亚语 | ka | 格鲁吉亚语 |
| sq | 阿尔巴尼亚语 | egy | 古埃及语 |
| ga / gd | 爱尔兰语/苏格兰盖尔语 | akk | 阿卡德语 |
| cy | 威尔士语 | mist | 未确定语源 |

表里没有的代码：按常识判断；实在不确定就保留原代码并写"（原文记作 xx）"，不要瞎编语言名。

## 非印欧语源 / 整词借入怎么讲
有些词不是从拉丁/希腊拼出来的，而是整词借入：阿拉伯语（assassin ← hashishīn、mask ← maskharah）、纳瓦特尔语（chocolate）、汉语（tea、ketchup）、意大利语（masquerade ← mascherata）。这类词的处理：
- 时间线照旧，只是第一层改成「借入层 + 源语言层」：`借入层（年代）→ 中间语言（法/意/西/葡）→ 源语言（阿拉伯语/纳瓦特尔语…）→ 字面 → 引申`。
- **不硬凑印欧词根**。词源文字里几个互相竞争的假说（mask 的阿拉伯语说 / 普罗旺斯语说 / 前印欧底层说），压成一句"来源有争议，比较主流的说法是……"，不要把几种猜测全抄给用户。
- 「归属词根」：能收拢同族词的可辨识词干就写它（masquerade → `masc`，见 `roots-glossary.md`「借词词干型词根」）；完全孤立的整词（chocolate、ketchup）写「无可分离词根，不入库」，不要硬造一个家族。
- 这类词的用户价值在"故事 + 字面义"，讲清借入时的画面感即可。

## etymonline 正文清理（它常带考证碎屑）
etymonline 是英文散文，会混进这些内容，**一律舍去不要输出**：
- 方括号引用：`[Karttunen]`、`[See Walther von Wartburg, "Französisches Etymologisches Wörterbuch…"]`。
- 交叉引用：`(q.v.)`、`(see mask (v.))`、`compare Bedouin`。
- 结尾样板尾巴：`also from 1530s`、`also from c. 1600`（网站元数据，不是词源）。
- 与主线无关的义项堆叠（chocolate 里 1723 年形容词、1845 年 chocolate milk、1940 年 chocolate-chip 之类）→ 最多保留 1–2 个与"为什么是这个意思"相关的义项转折。
- 只保留：首见年代 + 主要来源语言链 + 字面义 + 关键义项演变，压成 4–6 行中文时间线。

## 输出模板（中文）
```
**comprehend 词源脉络**

1. 借入层：14 世纪经中古英语 comprehenden，进入英语
2. 拉丁层：← 拉丁语 comprehendere（"to grasp"，抓住）
   = com-（一起、完全）+ prehendere（抓住）
3. 字面 → 引申：把东西整个抓住 → 领会、理解 → 包含
4. 印欧层（可选）：可追溯到原始印欧语词根 *gʰed-（抓住）
5. 同源旁支：comprehension、comprehensive、apprehend、prison

**归属词根**：prehend（抓住）；com- 只作拆解中的普通前缀
**入库状态**：findWord 显示还没入库 —— 要我加进 `prehend` 家族吗？
```

要点：
- 一层一行，每行都写清「语言 + 词形 + 含义」，链条要能一路读下来。
- 「字面 → 引申」必须单独给一行，这是用户最想要的部分。
- 最后给「归属词根」，拼写必须与 `roots-glossary.md` 的规范形式一致。
- 「归属词根」只列**家族名**：`roots-glossary.md` 里的规范词根，或「前缀兼作词根」表里列的前缀家族（anti/contra/pre/post/retro/pro/sub/super/trans/inter/extra/tele、auto/mono/poly 等）。com-/in-/de-/ex-/ad- 这种普通前缀只写在拆解里，**不要**替它们新建家族。
- 不要把 `{{...}}` 模板原文、英文长段落、文献引用贴给用户。
- 用户问的是派生形式（`-al`/`-ly`/`-ion` 这类派生词，如 architectural）时：先说明「X 是 Y 的派生形式」，再把 Y 的语源链条照常铺开，不要只说一句「派生自 Y」就结束。
- 中间层（法语/意大利语/西班牙语等）的拼写常与拉丁词根不同形（isolation ← 法语 isolé ← 拉丁 insula）：借入层照写现代拼写，**「归属词根」一律回填 `roots-glossary.md` 的规范形式**（isol → insul）。

## 实战样例
### 例 A：masquerade（借词 + 版式噪音，wiktionary）
原始返回（节选）：
```
thumb|People in masquerade (sense 2) at the {{w|Carnival of Venice}} in [[Venice, Italy, in 2015]]
The {{glossary|noun}} is borrowed from {{bor|en|frm|mascarade}}, {{m|frm|masquarade}}, {{m|frm|masquerade}}
... and its {{glossary|etymon}} {{der|en|it|mascherata|t=masquerade}}, from {{m|it|maschera|t=mask}} + {{m|it|-ata}}.
{{m|it||Maschera}} is derived from {{der|en|la-med|masca|t=mask}} ... cognate with {{cog|pt|mascarada}}, {{cog|es|mascarada}}.<ref>{{R:OED Online|...}}</ref>
```
应输出：
```
**masquerade 词源脉络**
1. 借入层：16 世纪英语借自中古法语 mascarade / masquarade（现代法语 mascarade 指假面舞会，也指闹剧）
2. 意大利层：← 意大利语 mascherata（假面舞会）= maschera（面具）+ -ata（表动作/集会）
3. 拉丁层：意大利语 maschera 出自中世纪拉丁语 masca（面具，也指鬼怪、梦魇）
4. 字面 → 引申：戴上面具的一场聚会 → 假面舞会 → 伪装、冒充
5. 同源旁支：mask、mascara、masquerader；法语 mascarade、葡萄牙语/西班牙语 mascarada

**归属词根**：masc（遮住脸的东西，假脸）
**入库状态**：findWord 显示还没入库 —— 要加进 `masc` 家族吗？
```
丢掉了：`thumb|...` 图片说明、`[[Venice, Italy, in 2015]]` 内链、`(sense 2)`、`{{glossary|noun}}`/`{{glossary|etymon}}`、`<ref>{{R:OED Online...}}</ref>`；`is cognate with` 只留成一行「同源旁支」。
注意第三段 "The {{glossary|verb}} is derived from the noun" 不必单独成行，可并入引申那句。

### 例 B：mask（etymonline 多假说，压缩示范）
etymonline 给了三个互相竞争的解释（阿拉伯语 maskharah / 普罗旺斯-日耳曼语源 / 前印欧底层 *mask-「黑」）。正确做法是压成：
```
**mask 词源脉络**
1. 借入层：16 世纪（1530s）从法语 masque 进入英语
2. 意大利-拉丁层：法语 masque ← 意大利语 maschera ← 中世纪拉丁语 masca（面具；也指鬼怪、梦魇）
3. 更早来源有争议，较主流的说法是阿拉伯语 maskharah（丑角、被嘲笑的人，出自 sakhira「嘲笑」）；也有学者认为来自普罗旺斯语 mask-「黑」（前印欧底层）
4. 字面 → 引申：遮住脸的东西 → 面具 → 伪装、掩饰（1570s）
5. 同源旁支：mascara、masquerade

**归属词根**：masc（遮住脸的东西，假脸）
```
丢掉了：`[Karttunen]`/`[See Walther von Wartburg, ...]` 方括号引用、`(q.v.)`/`(see mask (v.))` 交叉引用、结尾 `also from 1530s`。

### 例 C：isolation（借入层 + 变体拼写归并，wiktionary）
原始返回：
```
{{etydate|1800}}. From {{bor|en|fr|isolation}}, from {{m|fr|isolé}}, placed on an island (thus away from other people). Equivalent to {{suffix|en|isolate|ion}}.
```
应输出：
```
**isolation 词源脉络**
1. 首见：1800 年（`{{etydate|1800}}`）
2. 借入层：英语借自法语 isolation（隔离）
3. 法语层：← 法语 isolé（被放到岛上的 → 与人隔开），由 île / isole（岛）派生
4. 拉丁层：法语 isle、意大利语 isola ← 拉丁语 insula（岛）
5. 字面 → 引申：被放到一座孤岛上 → 与人隔绝 → 孤立、隔离（的状态）
6. 同源旁支：isolate、isolated、insular、peninsula、insulin；意大利语 isola、法语 île

**归属词根**：insul（岛）
**入库状态**：findWord 显示还没入库 —— 要我加进 `insul` 家族吗？
```
要点：
- `{{etydate|1800}}` 只给首见年代，写成「首见：1800 年」，不占一层语源链。
- `Equivalent to {{suffix|en|isolate|ion}}` 是构词说明，可并入一句「构词上＝isolate + -ion」，不单独成行。
- 现代拼写 `isol-`（法语/意大利语）≠ 拉丁规范词根 `insul-`：**归属词根一律写规范形式 `insul`**（反查表：isol → insul）。

### 例 D：architectural（cet_db 骨架 + 转查基词）
原始返回（**只有**一个 `{{ety}}` 骨架，没有语源内容）：
```
{{ety|en|:af|architecture|-al<id:adjectival>|text=+|tree=1}}
```
处理：`{{ety|...|tree=1}}` 是词源树目录，丢了就空了 → 转查基词 `architecture`（`source=cet_db`，`ipa=/ˈɑɹ.kɪˌtɛk.t͡ʃɚ/`，`level=CET4`）：
```
{{etymon|en|:bor|fr:architecture|tree=1}} {{root|en|ine-pro|*tetḱ-}} Borrowed from {{bor|en|fr|architecture}}, from {{der|en|la|architectūra}}. Originally from {{m|en|architect}}, from {{der|en|grc|ἀρχιτέκτων|t=architect|lit=arch builder, ext. chief builder, principal craftsman}}.
```
应输出：
```
**architectural 词源脉络**

architectural 是 architecture 的派生形容词（构词上＝architecture + -al），语源如下：

1. 借入层：16 世纪英语借自法语 architecture（建筑术）
2. 拉丁层：← 拉丁语 architectūra（建筑术），再 ← 拉丁语 architectus（建筑师）
3. 希腊层：← 古希腊语 ἀρχιτέκτων（"master builder"，总工匠）= ἀρχι-（首领、首要）+ τέκτων（建造者、木匠）
4. 印欧层：可追溯到原始印欧语词根 *tetḱ-（制作、建造）
5. 字面 → 引申：（首领级的）建造者所做之事 → 建筑术 → 建筑的、建筑学的
6. 同源旁支：architect、architecture、tectonic、tectonics

**归属词根**：arch（首领；首要）+ tect（建造者，工匠）
**入库状态**：findWord 显示还没入库 —— 要我加进 `arch` 和 `tect` 两个家族吗？
```
要点：
- 返回只有 `{{ety|...|tree=1}}` 骨架时**不要**当成「未收录」回复，也不要把模板原文丢给用户 —— 转查基词。
- `{{etymon|...|tree=1}}` 与正文里的 `{{ety|...|tree=1}}` 一样删掉；删掉后**还有正文**（如本例）就照常解码，删掉后**空无一物**（如 architectural 本体）才去转查基词。
- `architectural` 属于 `arch` + `tect` 两个家族；用户只问词源时**不自动入库**。

### 例 E：geocentricism（直接 404，靠构词补讲）
原始返回（工具层直接报错，没有 JSON 正文）：
```
tool invoke error: Request failed with status code 404 and {"error":"未找到 geocentricism 的词源信息"}
```
重试 `geocentrism`、`geocentric` 也是 404 → 说明「当前查询未找到可用词源」。以下仅是示例，实际状态必须重新调用工具确认：
```
**geocentricism 词源**

词源库未收录这个词（geocentricism / geocentrism / geocentric 都查不到），以下是按构词做的分析 —— 属我的判断，不是词典记载的词源。

1. 构词层：geo-（大地）+ centr-（圆心、中心点）+ -ic（形容词后缀）+ -ism（名词后缀，表学说、主义）
2. 字面义：以地球为（宇宙）中心点的（学说）
3. 引申义：地心说 —— 与 heliocentricism（日心说）相对
4. 同族旁支：geocentric、geocentrism、geography、geology、eccentric、concentrate

**归属词根**：geo（脚下的大地）+ centr（圆心，中心点）
**音标**：未标（该词词源查询返回 404，没有 `ipa` 字段）
**入库状态**：findWord 显示已在 `geo`、`centr` 两个家族里
```
要点：
- 404 表示当前查询未找到可用词源；503/超时表示查询不可用；换词典形重试一次即可收手。
- 404 没有 `ipa`，**绝不自己标音标**。
- 讲完构词分析照样可以入库；用户报新词时不要因为查不到词源就漏掉 `addWord`。
- 构词分析与词典词源要明确区分措辞。

## 质量自检（输出前过一遍）
- [ ] 变形词已还原成词典形后再查
- [ ] 已识别"未收录样板"，没有把网站简介当词源
- [ ] 没有把 `{{模板}}` 原文或 `<ref>` 引用丢给用户
- [ ] 没有大段照抄英文（etymonline 长文已压缩成时间线）
- [ ] 每个环节都有「语言 + 词形 + 含义」
- [ ] 给了「字面 → 引申」这一行
- [ ] 结论词根拼写与 `roots-glossary.md` 一致，且没有为 com-/in-/de- 这类普通前缀新建家族
- [ ] 图片说明行（`thumb|...`）、`[[内链]]`、`{{glossary|noun}}` 这类版式噪音已剥离
- [ ] etymonline 的方括号引用、`(q.v.)`、结尾 `also from ...` 样板尾巴已舍去
- [ ] 非印欧借词没有硬凑印欧词根；无可分离词根的整词没有硬造家族
- [ ] 借入词的中间层用现代拼写，但「归属词根」已回填 `roots-glossary.md` 的规范形式（isol → insul）
- [ ] 返回只有 `{{ety|...|tree=1}}` 骨架时已转查基词，没有当成「未收录」或把模板丢给用户
- [ ] `cet_db` 的正文残留（`1=== `、结尾 ` =`、`{{wikidata lexeme|...}}`、`{{noncog|...}}`）已剥离
- [ ] `ipa` 只在工具真的返回了非空值时才标，为 `null` 时不标也不自编
- [ ] 工具直接报 404 时已按「未收录」处理：换词典形重试一次、如实说明、不标音标、不跳过拆解
- [ ] 构词分析（我的判断）与词典记载的词源已明确区分措辞
- [ ] 分清了「词典收录的史实」和「我的推测」
- [ ] 工具真的被调用了，结果如实汇报

## 失败与降级
- 工具报错 / 网络失败：如实说"本次词源查询不可用"，可以凭词源知识给分析，但标注来源为"我的词源知识"，不得声称来自词典。
- 正文为空：说明本次无可用内容；只有模板骨架时先按前述规则转查基词一次，仍无内容再降级。
- 只查到 etymonline 长文而没有语源链：抽取最早年代 + 主要来源语言 + 关键义项演变，其余舍去。


## 词源记忆与证据边界
- 保留已有模板解码表、语言代码表、详细时间线与案例；它们用于学习词源记忆法。默认学单词时可浓缩成 2–4 行，用户要求深入时完整展开。
- 历史词源来自工具正文；现代构词说明与方便记忆的联想分别标注，不把自创故事、音近联想、未经证实的年代或词根当作词典事实。
- 上面示例中的“已入库”、音标、查询失败和年代都不能代替当前工具证据。基词的音标不能贴到派生词上。
- roots-glossary 中 centr 是规范词根（中心），cent 是百；不能再以 centr 为“未知词根”示例。查不到某个家族仅表示尚无该家族学习记录。
- 重试一次指最多再发起一次查询；不要照抄案例连续试多个猜测拼写。503/超时不进入“未收录”模板。
- 自造例句标“学习例句”，附中文理解；只查词源时不自动 addWord 或 saveLearningCard。用户希望记住这个词时才联动学习卡和后续复习。
