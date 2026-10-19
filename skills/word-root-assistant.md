---
name: word-root-assistant
description: 拆解英语单词的词源与词根、写出中文核心意象、生成英文例句，并调用 addWord 入库的完整工作流；含词根选取规则、输出模板、质量自检与易混词根速查。当用户报出新学的单词、询问词根家族、要某个词根的常见词，或问某个单词的词源历史时使用。
---

# 英语词根拆解工作流

## 何时使用
- 用户报出一个新学的单词（"我学了 retrospect""这个词怎么拆"）。
- 用户问有哪些词根家族、某个词根家族里有哪些词。
- 用户问某词根的常见词、常见词怎么拆。
- 用户只问"某个词的词源历史/词源/为什么是这个意思"（不入库）→ 用 skill `etymology-history` 的词源流程：`getEtymology(word)` 解码模板、还原变形词、避开"未收录样板"陷阱，再按需回到本流程入库。

## 标准步骤
1. **定词根**：判断词源，找出构成该词的所有成分（前缀/词根），并映射到规范拼写；只有一个成分入库一个，多个成分则逐个入库（见下"多根词"）。
2. **写核心意象**：一句中文，描述词根本身的动作或状态。
3. **写拆解逻辑**：`单词 = 前缀 + 词根(+后缀) = 字面义 → 引申义`。
4. **选例句**：优先用户原句；否则一句地道、书面语体的英文例句。
5. **入库**：`addWord(word, root, meaning, example)`。
6. **回报**：词根 / 核心意象 / 拆解 / 例句 / 入库结果。

## 词根怎么定
先查词源，再检验可能的前后缀；字形相似和“剥去前后缀后的剩余部分”都不能单独证明词根归属。以下列表只是候选线索：
1. 常见后缀：-tion/-sion, -ment, -able/-ible, -ive, -ate, -ous, -ity, -ize, -ance/-ence, -al, -ly, -er/-or。
2. 常见前缀：in-/im-, re-, con-/com-, de-, pro-, pre-, ex-/e-, sub-, trans-, ad-/ac-/af-, dis-, per-, ob-, inter-, retro-, post-, anti-。
3. 结合已查到的语源确认核心成分；出现变体时按 `roots-glossary.md` 映射到规范形式。
4. 判断词源：拉丁系取拉丁词根，希腊系取希腊词根（psychology → psych，geography → geo）。
5. 家族名只用 `roots-glossary.md` 里的规范词根，或「前缀兼作词根」表里的前缀（anti/contra/pre/post/retro/pro/sub/super/trans/inter/extra/tele、auto/mono/poly…）；com-/in-/de-/ex-/ad- 这类普通前缀只写进拆解，**不要**新建家族。
6. 一词含两个及以上独立家族成分时（前缀也当家族名用），每个成分都要入库，不要只选一个。
7. **拆不开的词**：若单词是从别的语言整词借入、内部没有可分离的前缀/词根（chocolate、ketchup、coffee），不要硬塞一个家族。能收拢同族词的可辨识词干（如 mask/masquerade/mascara → `masc`）按 `roots-glossary.md`「借词词干型词根」一节处理；完全孤立的整词不入库，只讲词源故事。

## 多根词（一个词入库到多个家族）
- 判定：前缀本身也是家族名时（见 `roots-glossary.md` 的"前缀兼作词根"表），该词同时属于前缀家族和词根家族。
- 例：`antibiotics = anti + bio + -tic(s)` → `addWord(root="anti")` 和 `addWord(root="bio")` **各调一次**，两次的 word/example 相同，meaning 各自填该成分的核心意象（anti = 挡在前面，对着干；bio = 活的东西，生命）。
- 例：`contradict = contra + dict` → contra、dict 各入库一次。
- 只入库一个家族是错误；两个家族都要能被 `readFamily` 查到。
- word 一律用词典原形、纯小写：用户报的 `antibiotics` 入库为 `antibiotic`。

## 核心意象怎么写
- 一句中文，最好 8 字以内，要能"看见画面"。
- 描述词根本身的动作/状态，不是某个单词的释义，也不是词典译文。
- 好例：spect = 眼睛扫过去，看；port = 搬着东西走，运送；tract = 用力拉，拽；rupt = 一下子断开，破。
- 差例：inspect = 检查（这是单词释义）；spect = 看的东西（没有画面、不准确）。

## 拆解逻辑怎么写
- 固定格式：`单词 = 前缀 + 词根(+后缀) = 字面义 → 引申义`。
- 例：inspect = in + spect = 向内看 → 检查；transport = trans + port = 横着搬过去 → 运输；retrospect = retro + spect = 向后看 → 回顾。

## 例句要求
- 优先使用用户给出的句子（可轻度修剪成完整句）。
- 用户没给时自造一句：完整英文句子，书面语体、8–20 词、能体现该词的典型搭配。
- 输出英文例句并附简短中文释义。自造句标作“学习例句”，没有试卷年份、卷别和来源不得标为真题。

## 回复模板（中文）
```
**retrospect**
- 音标：直接抄 `getEtymology` 返回的 `ipa`；没有 `ipa` 就删掉这一行，绝不自己拼
- 词根：retro（向后）＋ spect（眼睛扫过去，看）
- 拆解：retro(向后) + spect(看) = 向后看 → 回顾、回想
- 例句：In retrospect, that decision changed everything.
- 入库：仅在工具确认后，报告 retro、spect 两个家族的实际结果
```

## 列举某词根的常见词汇（用户说"给我 bio 词根的常见词"）
1. 先 `readFamily(root="bio")` 看已入库的词；家族不存在时后端返回 `404 {"error":"bio 家族不存在"}`，忽略错误继续下一步，不要因为报错就停。
2. 再凭你的词源知识列出该词根的常见词，每个词给三项：**单词 / 拆解 / 字面 → 引申**。
3. 用户说"入库"时，对列出的每个词调用 `addWord`；一个词含多个家族成分时（antibiotics = anti + bio），每个成分各调一次 `addWord`。
4. 只列真正含该词根的词，不要把同义但异源的词塞进家族。

## 四类请求的分流（先判断属于哪一类）
1. **添加新单词**（"我学了一个新词：retrospect"）→ 走「标准步骤」，必须调用 `addWord`，回报词根 / 核心意象 / 拆解 / 例句 / 入库结果。
2. **查询已有词根家族**（"spect 家族有哪些词"）→ `readFamily(root="spect")`，把返回的单词列表用中文展示给用户，不要直接甩 JSON；需要详细笔记时再调用 readNotes。
3. **列举词根的常见词**（"给我 bio 词根的常见词""anti 和 bio 能组成什么词"）→ 见上一节。
4. **查词源历史**（"comprehend 的词源历史""window 是怎么来的"）→ `getEtymology(word=词典形)`，按 skill `etymology-history` 解码成中文源流脉络；**不要自动入库**，讲完可以问一句"要不要入库"。另：`getEtymology` 查不到时会返回 etymonline 网站简介样板文字，那不是词源，必须识别并按"未收录"如实处理。

## 工具调用规则
- 入库：`addWord(word, root, meaning, example)`（单词、词根、核心意象、例句）
- 批量入库：`batchAdd(words=[{word, root, meaning}, ...])`，一次最多 100 条，返回 `details` + `summary{added,duplicate,error}`；批量加同一个词的多个词根时可用，支持每项附 example；多词根可在同一次 batchAdd 中提交。
- 列家族：`listRoots()` → `{"roots":[...]}`
- 查家族：`readFamily(root)`，root 传规范拼写
- 查家族笔记（含意象/例句表格）：`readNotes(root)`
- 反查单词属于哪些家族：`findWord(word)` → `{"word":..,"count":0,"families":[...]}`；入库前查重、讲词源后判断"是否已学过"时用。
- 删除单词：`deleteWord(word, root)` → `{"status":"ok","message":"已从 spect 家族删除 zzprobeword"}`。用户明确要求删除时使用；词族删除与学习卡复习记录是两个独立操作。
- 查词源：`getEtymology(word)` → `{"word":..,"source":"wiktionary|etymonline|cet_db","etymology":"...","ipa":"/əˈbæn.dən/"|"level":"CET4"}`；`ipa` 是可选字段（可能为 `null`），**只在有值时附音标，绝不自己拼**。解码规则见 skill `etymology-history`。
- 查词源失败：404 仅表示本次未找到可用词源段落，不等于词不存在；503/超时表示来源暂不可用。可换可信的词典形或基词重试一次，不要反复猜拼写。解释现状并继续提供明确标注为“构词分析/记忆联想”的帮助，音标缺失时不编造。是否入库仍按用户意图处理；不要把未经确认的家族推测写成事实。
- 用户只报单词时，不要做例行的 `listRoots`/`readFamily` 查询；只有两种情况例外：用户问家族，或词根拼写拿不准需要核对已有家族（此时只需 `listRoots`）。
- 必须真正调用工具；失败时如实汇报。
- `addWord` 失败时不要中断：照常输出完整分析，说明"本次未能写入词根库"+ 原因；能写文件时把记录追加到工作区 `root-families/<root>.md` 作本地备份并注明，不能写文件就只给分析。
- `listRoots`/`readFamily` 失败时说明查询不可用，只有本地备份存在时才可据其回答并标注来源，绝不编造。

## 质量自检（每次输出前过一遍）
- [ ] root 是规范拼写、纯小写字母、不含前后缀
- [ ] meaning 描述的是词根，不是这个单词
- [ ] 拆解里每个前缀/后缀都解释得到，能自圆其说
- [ ] 例句是完整、地道的英文句子
- [ ] word 用的是词典原形且小写（antibiotics → antibiotic）
- [ ] 多根词：每个成分家族都调了一次 addWord，没有漏
- [ ] 工具确实被调用，结果如实汇报
- [ ] 只问词源的需求没有擅自入库（应询问用户）
- [ ] 无可分离成分的整词借入（chocolate 这类）没有硬凑家族；可收拢词干的（masc）用的是 glossary 里的规范拼写
- [ ] 音标只取 `getEtymology` 返回的非空 `ipa`，没有就整行不写；音标逐字照抄，绝不自编
- [ ] `getEtymology` 直接 404 时按「词源库未收录」处理：最多换词典形重试一次、不编音标、说明证据限制；仅保存可靠归属

## 易混词根速查
- spect（主动看、审视）vs vis（看见、视觉）：inspect/respect → spect；visible/vision → vis
- cad（落下）vs cis（切、杀）：accident → cad；decide/homicide → cis
- ver（真）vs vert（转）：verify → ver；convert/reverse → vert
- lect（选、读、收集）vs leg（法律）：collect → lect；legal → leg
- capit（头）vs cap（抓、拿）：capital → capit；capture/accept → cap
- pass（走）vs pat（受苦）：passage → pass；patient/passion → pat
- masc（面具）vs mask：所有含 mask/mascara/masquerade 的词一律归 `masc`，不要新建 `mask` 家族
- dict（说）vs dic：规范拼写是 `dict`（predict/dictate/contradict/dedicate 全归 `dict`），不要新建 `dic` 家族
- geo（大地）vs gen（出生、产生）：geography/geocentric/apogee → geo；generate/genetic → gen
- cent（一百）vs centr（圆心、中心点）：century/percent/centipede → cent；central/eccentric/concentrate → centr
- tect（建造者、工匠）vs techn（技艺、手艺）vs text（编织）：architect/architecture/tectonic → tect；technology/technique → techn；textile/context → text
- 完整对照与全部规范拼写见工作区文件 `roots-glossary.md`；找不到该文件时按自己的词源知识判定，并保持拼写一致

## 附录：无 `roots-glossary.md` 时的兜底清单
工作区有 `roots-glossary.md`（规范词根总表 / 变体反查表 / 易混对照 / 前缀兼作词根表 / 借词词干型词根）时一律以它为准。
文件不在时，用下面清单保证"同一词根永远只用一个拼写"。

**规范词根名与家族名前缀（共 257 个，纯小写、不含前后缀）**：
act, ali, alt, ambul, anim, ann, anti, aqua, arch, aster, aud, aug, auto, bene, bio, brev, cad, cap, capit, carn, ced, celer, cent, centr, cern, cert, chron, circum, cis, civ, claim, clar, clud, cogn, contra, cord, corp, cre, cred, crypt, culp, cur, cura, dat, dem, dent, dia, dict, dign, doct, dorm, duc, dur, dyn, empt, epi, equ, err, eu, extra, fac, fals, fer, fess, fid, fin, flect, flu, foli, form, fort, fract, frat, frig, fug, fund, gam, gen, geo, grad, graph, grat, grav, greg, her, horr, hosp, hydr, hyper, hypo, insul, inter, it, ject, jud, junct, juven, lab, lat, later, lect, leg, lev, liber, lingu, liter, loc, log, loqu, luc, lud, magn, mal, man, mar, masc, mater, med, mem, ment, merg, meta, metr, migr, min, mir, mit, mob, mon, mono, morph, mort, mult, mun, mut, nat, nav, neg, nom, norm, not, nov, numer, nur, ocul, omni, oper, opt, pac, pan, par, para, part, pass, pat, patr, ped, pel, pend, pet, phon, photo, plac, ple, plic, poly, pon, popul, port, post, pot, pre, prehend, prim, priv, pro, prob, proto, pseudo, psych, puer, punct, put, quer, quiet, radi, rat, rect, retro, rog, rupt, sacr, sal, san, sci, scop, scrib, sect, sed, sens, sequ, serv, simil, soci, sol, solv, somn, son, soph, spect, sper, spir, sta, stell, stru, sub, sum, super, surg, syn, tact, tain, techn, tect, tele, tempor, tend, termin, terr, test, text, the, therm, tort, tract, trans, tribut, turb, ultim, un, urb, util, vac, vad, val, ven, ver, verb, vert, vestig, via, vict, vis, viv, voc, volv, vor

**高频变体 → 规范形式**（左列出现在单词里时，`addWord(root=...)` 一律用右列，共 140 条）：
ag→act；alter→ali；archi→arch；astr→aster；auct→aug；audit→aud；bon→bene；capt→cap；cas→cad；ceed→ced；centi→cent；centro→centr；cept→cap；cess→ced；cid→cis；cip→cap；clam→claim；clos→clud；clus→clud；cour→cur；cresc→cre；crim→cern；curs→cur；dic→dict；doc→doct；don→dat；dot→dat；duct→duc；dynam→dyn；em→empt；enn→ann；fact→fac；fect→fac；fic→fac；flex→flect；flux→flu；found→fund；frag→fract；frater→frat；gee→geo；gnos→cogn；gram→graph；gress→grad；hes→her；ig→act；isol→insul；join→junct；jur→jud；jus→jud；laps→lab；leg→lect；lig→lect；locut→loqu；logy→log；lum→luc；lus→lud；lustr→luc；manu→man；mari→mar；mascar→masc；masch→masc；mask→masc；masqu→masc；matr→mater；medi→med；memor→mem；mens→metr；mers→merg；miss→mit；monit→mon；mot→mob；mov→mob；muner→mun；nasc→nat；nour→nur；nutri→nur；nym→nom；pass→pat；pater→patr；pens→pend；petit→pet；plen→ple；plet→ple；plex→plic；ply→plic；pod→ped；point→punct；pos→pon；poss→pot；pound→pon；prehens→prehend；prin→prim；prov→prob；publ→popul；puls→pel；quest→quer；quie→quiet；quir→quer；reg→rect；sanct→sacr；sanit→san；script→scrib；secut→sequ；seg→sect；sent→sens；sess→sed；sid→sed；simul→simil；sist→sta；solu→solv；spec→spect；spic→spect；stat→sta；stit→sta；struct→stru；sult→sal；sumpt→sum；surrect→surg；sym→syn；tag→tact；tang→tact；techni→techn；techno→techn；ten→tain；tens→tend；tent→tend；theo→the；tin→tain；uni→un；vail→val；van→vac；vas→vad；vent→ven；vers→vert；vid→vis；vinc→vict；vit→viv；void→vac；vok→voc；volut→volv


## CET 学习与复习补充（与主提示词配套）
- 目标始终是通过词源和词根理解、记住并使用词汇。保留字面义到引申义的桥梁；讲词源历史时继续使用 etymology-history 的完整流程。
- 用户报词要学习、或明确要求入库：先 findWord/getEtymology，讲常用义、词源记忆、1–2 个搭配、例句及中文释义；可靠词根用 addWord/batchAdd 入库，再 saveLearningCard 保存单词级记录。仅查词源、快速查义或列候选词，不自动保存。
- 学习卡的 definition 是单词释义，家族工具 meaning 是词根核心意象，不能混用。level 由后端本地词表决定。source_note 必须区分工具所给词源与模型补充。不可拆的词也能建卡，roots 留空。
- 不把入库当作掌握。用户说“复习”调用 reviewQueue；语境测验调用 quiz，一次一题，等待答案后才 answerQuiz。答题后再讲词源与搭配。用户自评时用 recordReview；不替用户自评，不重复登记 answerQuiz 已计入的复习。
- 用户要求按四级/六级选词时调用 studyWords，默认每批 5 个；依照用户节奏学习，不自动把全部候选入库。
- 旧笔记不会自动变成学习卡。复习旧词时先读已有资料再补建卡，保留原来词根分类。默认不增加冗长家族查询；用户询问家族时再查。
- 多根词只建一张单词学习卡，但每个可靠家族都登记。com/in/de/ex/ad 等普通前缀只用于拆解；glossary 中允许的 anti/retro/arch 等才作家族。
