# แบบทีม AI ส่วนตัวสำหรับ Orca

วันที่ค้นคว้า: 18 ตุลาคม 2026 · เป้าหมาย: ใช้ subscription ที่มีอยู่ก่อน

ข้อเสนอคือ **Leader 1 ตัว ใช้ Sol หรือ Opus + worker ที่เปิดตามงาน 2–4 ตัว + skill เฉพาะด้านที่โหลดเมื่อจำเป็น** จำนวนบทบาทไม่เท่ากับจำนวน agent ที่ต้องเปิดพร้อมกัน งานเล็กใช้ Leader ตัวเดียวได้

เอกสารนี้เป็นแบบออกแบบและแม่แบบ ยังไม่ได้ติดตั้ง skill เปลี่ยนบัญชี หรือเปิด worker จริง

## หลักฐานที่ใช้และช่วงเวลา

ให้ความสำคัญกับ 18 เมษายน–18 ตุลาคม 2026 และใช้บางแหล่งช่วงมกราคม–มีนาคม 2026 ตามเงื่อนไข “ภายในปีนี้” ไม่ใช้บทความปี 2025 เป็นหลักฐาน เอกสารออนไลน์ที่ไม่มีวันเผยแพร่ระบุว่าเป็นสถานะที่ตรวจวันที่ 18 ตุลาคม ไม่อ้างว่าวัน crawl คือวันเผยแพร่

| แหล่งโดยตรง | วันที่ | สิ่งที่นำมาใช้ |
|---|---|---|
| [Cursor: Agent swarms and the new model economics](https://prod.cursor.com/blog/agent-swarm-model-economics) | 20 ก.ค. 2026 | แยก planner กับ worker และประเมินการใช้โมเดลต่างกัน; เป็นการทดลองเฉพาะงาน ไม่ใช่ตัวเลขรับประกันความประหยัด |
| [Addy Osmani: Audit your Agent files](https://addyosmani.com/blog/audit-your-agent-files/) | 27 ส.ค. 2026 | ตรวจทบทวน instruction และ skill ที่สะสม; กฎที่ต้องบังคับจริงควรมีเครื่องมือหรือ permission รองรับ |
| [Addy Osmani: Long-running Agents](https://addyosmani.com/blog/long-running-agents/) | 28 เม.ย. 2026 | ออกแบบ state และผลส่งมอบให้ทำงานต่อข้าม session ได้ |
| [Anthropic: AWS Summit LA](https://www.anthropic.com/events/anthropic-at-aws-summit-la-2026) | งาน 10 มิ.ย. 2026 | แนวทาง context แบบเรียกข้อมูลเมื่อจำเป็น, compaction, structured memory และ subagent |
| [Anthropic: Harness design](https://www.anthropic.com/engineering/harness-design-long-running-apps) | 24 มี.ค. 2026 | ใช้เกณฑ์ประเมินและ feedback loop ที่ตรวจผลได้ |
| [Anthropic: Building a C compiler](https://www.anthropic.com/engineering/building-c-compiler) | 5 ก.พ. 2026 | ตัวอย่าง parallel agents ที่ต้องมี test และแบ่งงานได้จริง; ขนาดการทดลองไม่เหมาะจะลอกมาใช้กับงบส่วนตัว |
| [OpenAI Docs: Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents) | ตรวจ 18 ต.ค. 2026; หน้าไม่ระบุวันเผยแพร่ | กำหนดโมเดลลูกได้; เหมาะกับการแยกงานอ่านและคืนข้อค้นพบ; ต้องระวังการแก้ไฟล์พร้อมกัน |
| [Claude Code: Subagents](https://code.claude.com/docs/en/sub-agents) | ตรวจ 18 ต.ค. 2026; หน้าไม่ระบุวันเผยแพร่ | กำหนด model และ tool ของแต่ละบทบาท |
| [Claude Code: Agent teams](https://code.claude.com/docs/en/agent-teams) | ตรวจ 18 ต.ค. 2026; หน้าไม่ระบุวันเผยแพร่ | ทีมมี context แยกกันและใช้ token เพิ่มตามงานของสมาชิก |
| [Claude Code: Costs](https://code.claude.com/docs/en/costs) | ตรวจ 18 ต.ค. 2026; หน้าไม่ระบุวันเผยแพร่ | ใช้โมเดลตามงาน, โหลด skill เมื่อจำเป็น และประมวลผล log ก่อนป้อนเข้าโมเดล |

นี่เป็นข้อสังเคราะห์จากตัวอย่างผู้พัฒนาและทีมชั้นนำ ไม่ใช่ข้ออ้างว่าผู้พัฒนาทั่วโลกใช้ setup เดียวกัน ตัวเลขและเพดานด้านล่างเป็นค่าเริ่มต้นที่เสนอให้ทดลองกับงานคุณ

## โครงสร้างทีม

```text
คุณ
 └─ Leader: Sol / Opus
     ├─ Scout × N       ค้นและอ่าน code, เอกสาร, log
     ├─ Researcher × N  หาข้อมูลภายนอกและหลักฐาน
     ├─ Builder × N     เขียน code / content / เอกสาร / asset
     ├─ Verifier × N    ทดสอบผลและตรวจข้อเท็จจริง
     ├─ Reviewer        ตรวจข้อบกพร่องอิสระตามความเสี่ยง
     └─ Operator        เตรียมส่งมอบและติดตามผล

Orca: task, dependency, dispatch, inbox, worktree และสถานะ
ไฟล์: brief, contract, artifact, หลักฐาน และบันทึกตัดสินใจ
```

Account routing เป็นกติกาและข้อมูลของตัวจัดการงาน ไม่ต้องมี LLM “Account Manager” อีกตัว

| บทบาท | ความรับผิดชอบและผลส่งมอบ | โมเดลเริ่มต้น | จำนวนที่เปิดเมื่อจำเป็น |
|---|---|---|---|
| Leader | เข้าใจเป้าหมาย กำหนดเงื่อนไขสำเร็จ ออกแบบ เลือกโมเดล แบ่งงาน ตัดสินใจ และสรุปให้คุณ | Sol หรือ Opus | 1 ต่อโครงการที่กำลังคุย |
| Scout | ค้นก่อนอ่าน อ่านเฉพาะขอบเขต ส่งข้อค้นพบพร้อม path/line และสิ่งที่ยังไม่ตรวจ | Luna; Sonnet เมื่ออ่านตรรกะซับซ้อน | 1–4 |
| Researcher | ตอบคำถามวิจัยที่ชัดเจน พร้อม URL วันที่ ข้อเท็จจริง ข้อขัดแย้ง และข้อจำกัด | Luna สำหรับรวบรวม/สกัด; Sonnet สำหรับสังเคราะห์ย่อย | 1–3 |
| Builder | ทำชิ้นงานตาม contract และเป็นเจ้าของชุดไฟล์ที่ได้รับ | Luna สำหรับงานชัดเจน; Sonnet สำหรับ implementation ที่ซับซ้อนขึ้น | 1–3 |
| Verifier | ตรวจ acceptance criteria, รัน test หรือ fact-check และเก็บหลักฐาน | Luna; Sonnet สำหรับออกแบบ test ยาก | 1–2 |
| Reviewer | ตรวจ diff และผลลัพธ์โดยอิสระ หา regression/ช่องโหว่/ข้อกล่าวอ้างเกินหลักฐาน | Sonnet; Sol/Opus สำหรับจุดเสี่ยงสูง | 0–1 |
| Operator | release note, PR package, deployment/publishing plan, rollback และผลวัดหลังส่งมอบ | Luna หรือ Sonnet | 0–1 |

บทบาท Reviewer อาจรันเป็นงานใหม่ใน worker slot เดิมหลัง Builder จบ แต่ใช้ context ใหม่ ไม่ต้องเปิดรอถาวร Leader รับบท Product/Architect เองในงานทั่วไป และแยก Architect เพิ่มเฉพาะเมื่อโครงการใหญ่พอ

## การเลือกโมเดล

ปริมาณข้อความมากไม่ได้แปลว่างานง่าย ให้ Leader ประเมินสองแกนคือ **ปริมาณข้อมูล** และ **ความยาก/ผลเสียหากผิด**

| ลักษณะงาน | การตัดสินใจ |
|---|---|
| สกัด field, ค้น symbol, สรุปไฟล์รายโมดูล, แก้ข้อความตาม pattern | Luna, effort ต่ำตามที่โมเดลรองรับ |
| code change ที่มีขอบเขตและ test ชัด | ลอง Luna ก่อนเมื่อเหมาะ; ใช้ Sonnet หากมี Claude และงานต้องใช้เหตุผลมากขึ้น |
| ไล่ state ข้าม service, test design, debugging ที่ไม่ชัด | Sonnet หรือ Sol ตามความยาก |
| architecture, เป้าหมายคลุมเครือ, หลักฐานขัดแย้ง, auth/payment/data migration | Sol/Opus สำหรับการตัดสินใจและ review สำคัญ |
| เขียนบทความจำนวนมากจาก fact sheet ที่ตรวจแล้ว | Luna/Sonnet; ให้ Reviewer ตรวจ claims และภาษา |

ใช้ชื่อโมเดลจริงที่บัญชีเข้าถึงได้ และตรวจผลการ launch ไม่พึ่งชื่อ role โมเดลของ worker ไม่ควร inherit จาก Leader โดยไม่ตั้งใจ หากเปลี่ยนโมเดลให้คง task และหลักฐานเดิม แล้วเพิ่มเฉพาะบริบทที่จำเป็น

Codex มี Sol/Luna ในเอกสารปัจจุบัน และ Claude Code รองรับการระบุ Opus/Sonnet สำหรับ subagent แต่ subscription, workspace policy และเวอร์ชัน client มีผลต่อสิทธิ์ใช้งาน ดู [OpenAI model selection](https://developers.openai.com/api/docs/guides/model-selection) และ [Claude subagents](https://code.claude.com/docs/en/sub-agents)

ไม่ถือว่า Sonnet มีราคา/ความเร็วเท่ากับ Luna และไม่ใช้ราคา API มาแปลงเป็นโควตา subscription โดยตรง

## หนึ่งบัญชีและหลายบัญชี

| บัญชีที่มี | รูปแบบทีม |
|---|---|
| Codex 1 บัญชี | Sol Leader + Luna worker; เริ่ม worker พร้อมกัน 2 ตัว และใช้โควตาบัญชีเดียวร่วมกัน |
| Claude 1 บัญชี | Opus Leader + Sonnet worker; งานสกัดง่ายมากอาจทดลอง Haiku หากมีสิทธิ์ |
| Codex + Claude | เลือก Leader หลักเพียงตัวเดียว; ใช้ Luna ทำงานจำกัดขอบเขต และ Sonnet ทำ implementation/review ตามความเหมาะสม |
| Codex ส่วนตัว 2–3 บัญชี | จัด pool ตามบัญชีที่คุณมีสิทธิ์ใช้งานจริง เก็บ session/credentials แยก และกำหนด worker cap รวม |
| มีบัญชีบริษัทเพิ่ม | แยก workspace, Leader, artifacts, logs, memory และ connectors สำหรับงานบริษัททั้งเส้นทาง |

ตัวอย่างชื่อเชิงนโยบาย: `personal-codex-a`, `personal-codex-b`, `personal-claude`, `company-codex` ชื่อเหล่านี้ไม่ใช่ agent ID หรือ config key ที่ Orca รับโดยอัตโนมัติ

กติกาการจัดสรร:

1. จัดประเภทข้อมูลและงานก่อน: personal หรือ company จากนั้นกรองบัญชีที่ได้รับอนุญาต
2. เลือกโมเดลที่เพียงพอกับงานจากบัญชีที่ผ่านการกรอง แล้วดูความพร้อมและโควตาที่ตรวจได้
3. จำกัด concurrency รวมทั้งระบบ เริ่ม 2 worker/บัญชีและรวมไม่เกิน 4 worker เป็นค่าทดลอง ไม่ใช่เพดานผู้ให้บริการ
4. เมื่อบัญชีติด limit ให้ checkpoint และรอ หรือส่งต่องานไปช่องทางที่อนุญาตและตรวจ identity แล้ว; ไม่ถือว่ามี quota pool รวม
5. ถ้า quota อ่านผ่านเครื่องมือไม่ได้ ให้บันทึกว่า unknown และใช้ข้อมูลที่ UI แสดง ไม่เดาตัวเลข
6. ไม่ส่งแม้แต่ summary ของข้อมูลบริษัทให้ Leader ในบัญชีส่วนตัว เว้นแต่องค์กรอนุญาตชัดเจน

หลายบัญชีเพิ่มช่องทางทำงานที่ได้รับอนุญาต แต่ไม่ลดจำนวน token ที่งานต้องใช้ และไม่ทำให้ context หรือโควตารวมกันเอง

### สิ่งที่ตรวจจาก Orca ในเครื่องได้จริง

ตรวจคู่มือ runtime และ `--help` วันที่ 18 ตุลาคม 2026 แล้ว:

- `orchestration worker-start` มี `--agent`, `--model`, `--effort`, `--deps`, `--worktree` และการ reuse terminal
- คู่มือกำหนดให้เทียบ `launch.requested` กับ `launch.effective` ก่อนยืนยันโมเดล/effort
- ไม่พบ `--account` ในคำสั่งเริ่ม worker ที่ตรวจ และ help ของ account บางคำสั่งครอบคลุม provider ต่างกัน จึงยังยืนยันการเลือกบัญชี Codex/Claude ใด ๆ ต่อ worker ผ่าน CLI ไม่ได้
- ฉะนั้นการ route หลายบัญชียังต้องตรวจจากตัวเลือกบัญชี/agent profile ที่ Orca build นี้รองรับจริง หากเลือกต่อ launch ไม่ได้ ให้เตรียม session ที่ล็อกอินถูกบัญชีแล้วและยืนยันก่อนใช้; ถ้าผูก supervised worker กับ session นั้นอย่างถูกต้องไม่ได้ ให้ใช้บัญชี default ที่ยืนยันแล้วหรือรอ ไม่สลับ login ส่วนกลางระหว่างงาน
- นโยบายในเอกสารนี้ไม่ได้ทำให้ Orca มี scheduler, account router หรือ hard token cap โดยอัตโนมัติ

หลักฐานเพิ่มเติมอยู่ใน [บันทึกความสามารถ Orca](orca-capabilities.md)

## ทุก process ในวงจรงาน

| ขั้น | เจ้าของ | หลักฐาน/ผลส่งมอบก่อนผ่านขั้น |
|---|---|---|
| รับโจทย์และคัดเป้าหมาย | Leader | ปัญหา ผู้ใช้เป้าหมาย ข้อจำกัด และผลลัพธ์ที่ต้องการ |
| สำรวจระบบ/ตลาด | Scout + Researcher ขนาน | ขอบเขตที่ตรวจและสิ่งที่ยังไม่รู้ พร้อมหลักฐาน |
| ออกแบบและจัดลำดับ | Leader | brief, contract, dependency, file ownership และเกณฑ์สำเร็จ |
| สร้าง | Builder หลายตัวเมื่ออิสระ | artifact/diff และหมายเหตุการเปลี่ยนแปลง |
| ตรวจผล | Verifier | test result หรือ claim checklist ที่ตรวจจริง |
| ตรวจความเสี่ยง | Reviewer ตามระดับงาน | ข้อบกพร่องที่ระบุความรุนแรงและหลักฐาน |
| แก้และรวม | เจ้าของชิ้นงาน; Leader ตัดสินใจ | แก้ข้อบกพร่องและตรวจบนชุดไฟล์ที่รวมแล้ว |
| ส่งมอบ | Operator + Leader | preview/PR/release package ที่พร้อมตรวจ |
| ปล่อยใช้/เผยแพร่ | ทำตามสิทธิ์ที่คุณกำหนดไว้ | ผลการปล่อยใช้งานและแนวทางย้อนกลับ |
| ดูแลและเรียนรู้ | Operator/Verifier เมื่อมีเหตุ | metric, incident/repro, งานแก้ และบทเรียนที่ตรวจแล้ว |

เงื่อนไขอนุมัติต้องตั้งตามสิทธิ์จริง ไม่ถามซ้ำเมื่อคุณอนุญาตแล้ว การ review ไม่จำเป็นต้องเป็น agent แยกสำหรับทุกงานเล็ก แต่ต้องมีวิธีตรวจผลที่เหมาะกับงาน

## Parallel ให้เร็วโดยไม่ซ้ำงาน

**เริ่มจากคลื่นงานที่อิสระทั้งหมดก่อนรอผล** ไม่เรียก reader ตัวหนึ่งแล้วรอจนจบก่อนเริ่มตัวถัดไป

ตัวอย่างเพิ่มระบบ subscription:

```text
คลื่น 1: Scout-A อ่าน backend billing
         Scout-B อ่าน frontend/account
         Scout-C อ่าน schema + existing tests
         Researcher-D ตรวจ provider API เฉพาะที่ต้องใช้
              ↓
Leader ตัดสินใจ contract และ invariant ร่วม
              ↓
คลื่น 2: Builder-A backend      Builder-B frontend
         Verifier-C เตรียม test จาก contract ได้พร้อมกัน
              ↓
รวม changes → integration test → review จุดเสี่ยง → ส่งมอบ
```

แบ่งตามโมดูล/คำถาม/ชุดเอกสาร และประมาณปริมาณข้อมูลก่อน ไม่แบ่งตามจำนวนไฟล์เท่า ๆ กัน เพราะขนาดและความยากต่างกัน ถ้ามีไฟล์ใหญ่ไฟล์เดียว แยกตามหัวข้อหรือ symbol หลังทำสารบัญสั้น ๆ

สำหรับอ่าน repo ใหญ่ เริ่ม `rg --files`, ค้น symbol หรือ error แล้วอ่านช่วงที่เกี่ยวข้อง ใช้หลาย reader เมื่อมีหลายขอบเขตจริง รายงานต้องระบุบริเวณที่ไม่ได้อ่าน ห้ามสรุปว่าอ่านครบจากการสุ่มบางไฟล์

งานเขียนแต่ละตัวมีชุดไฟล์รับผิดชอบชัดเจน Shared schema, lockfile และ config กลางมีเจ้าของหนึ่งคน ถ้าต้องแยก worktree ให้เริ่มจากฐานที่ตกลงร่วมและรวมเป็นขั้นตอน; worktree แยกไม่ได้ป้องกัน semantic conflict จึงต้องมี integration check ส่วนโปรเจกต์ที่เป็น folder ไม่มี Git ให้แบ่งโฟลเดอร์และจำกัดผู้แก้แต่ละไฟล์

worker ห้าม spawn ลูกเองเป็นค่าเริ่มต้น ถ้าต้องแตกงานให้ขอ Leader จัดสรรจากเพดานรวม ป้องกัน Orca workers × native subagents เพิ่มจำนวนโดยไม่รู้ตัว

## ควบคุม token และโควตา

1. **เป้าหมายคือค่าใช้จ่าย/โควตาต่อผลงานที่ผ่านตรวจ** พร้อมเวลา ไม่ใช่บังคับให้ทุก request สั้นที่สุดจนต้องอ่านใหม่หรือแก้ซ้ำ
2. Leader ถือ brief, decisions, contracts และข้อค้นพบเป็นหลัก ไม่รับ transcript ของ worker ทั้งหมด
3. ใช้ context ใหม่สำหรับงานใหม่ และส่งเฉพาะข้อมูลที่งานลูกต้องใช้; reuse session เมื่อเป็นงานต่อเนื่องและมีประโยชน์จากบริบทเดิม
4. รายงาน worker ตั้งเป้า 300–700 token เป็น soft limit พร้อม path ไปผลเต็ม ถ้างานต้องแสดงหลักฐานมากขึ้นให้ขยายได้ ภาษาไทยต้องใช้ tokenizer ที่ตรงรุ่นหากต้องการตัวเลขจริง
5. เก็บ raw log ไว้ไฟล์ ให้ agent เห็น failure, exit code และตำแหน่งรายงานก่อน; อย่ากรองจนซ่อน error หรือทำให้ exit code เปลี่ยน
6. เปิด skill ที่จำเป็นต่อขั้นงาน อย่าป้อนทั้งคลังเข้า system prompt; ให้ AGENTS.md/CLAUDE.md มีเฉพาะกติกาและข้อควรรู้ที่ค้นเองไม่ง่าย ตั้งเป้าร่างเริ่มต้นราว 60–120 บรรทัด ไม่ใช่ข้อจำกัดทางเทคนิค
7. Context/checkpoint เก็บ goal, decisions, paths, commit/base, สิ่งที่ลองแล้ว, failures และ next action; ก่อนใช้ summary ต้องตรวจว่ายังตรงกับ state ปัจจุบัน
8. ใช้ stable instructions เพื่อช่วยการใช้ cache ที่ runtime รองรับ แต่ไม่ถือว่า cache แชร์ข้ามบัญชี/provider/session หรือเปลี่ยนโมเดลแล้วใช้ต่อได้เสมอ
9. ใช้ deterministic tools เช่น search, parser, formatter, compiler และ test runner ก่อนเรียก LLM สำหรับงานที่เครื่องมือทำได้
10. ถ้าลองแก้ปัญหาแบบเดิม 2 รอบแล้วยังไม่คืบหน้า ให้ส่งหลักฐานกลับ Leader เพื่อเปลี่ยนวิธีหรือโมเดล ไม่ให้ loop ไปเรื่อย ๆ
11. รอ event/inbox และดูสถานะเฉพาะที่ต้องตัดสินใจ แทนการอ่าน transcript ทุกตัวซ้ำถี่ ๆ
12. ให้ budget warning เป็นจุดทบทวนและ checkpoint ไม่ใช่เหตุให้ประกาศว่างานเสร็จ

Soft token/time budget ใน prompt ไม่ใช่ hard enforcement หากต้องการบังคับจริงต้องมี runtime support หรือ controller ที่นับ usage และจัดการการหยุด/กู้คืนอย่างถูกต้อง สำหรับ subscription เริ่มจากดู quota bar/reset ที่ตรวจได้และเวลาต่อชิ้นงาน

## Skill ที่คัดเลือก

ตัวเลขเป็นค่าประมาณที่หน้า directory แสดงระหว่างค้นวันที่ 18 ตุลาคม 2026 อาจต่างกันตาม snapshot; install/star เป็นสัญญาณความนิยม ไม่ใช่การรับรองคุณภาพหรือความปลอดภัย แหล่ง technical ตรวจร่วมกับ repo ต้นทาง

| Skill / แหล่ง | ใช้กับใครและเพื่ออะไร | สัญญาณที่ตรวจ | ข้อเสนอ |
|---|---|---|---|
| Orca `orchestration` + `orca-cli` | Leader คุม task, dependency, inbox และ worktree ด้วยคำสั่งจริง | คู่มือตรงกับ binary ในเครื่อง; ไม่มียอด marketplace ที่ตรวจ | ใช้แกนหลักตามประเภทงาน โหลด reference เฉพาะที่ต้องใช้ |
| [context-optimization](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering/blob/main/skills/context-optimization/SKILL.md) | ออกแบบ context budget และลดข้อมูลที่ไม่เกี่ยวข้อง | repo ราว 18.2K stars; ยอด skill นี้ตรวจไม่ได้; metadata ระบุอัปเดต 15 พ.ค. 2026 | ทดลองเฉพาะตอนปรับระบบ ไม่โหลดทุก task และไม่ถือค่าประหยัดในคู่มือเป็นผลพิสูจน์ |
| [context-compression](https://www.skills.sh/muratcankoylan/agent-skills-for-context-engineering/context-compression) | checkpoint/handoff ในงานยาว | 424 installs; repo 18.2K stars; First Seen 20 ม.ค. 2026 | กลุ่มทดลอง: ยอดราย skill ยังต่ำกว่า 1K ต้องเทียบผลจริง |
| [filesystem-context](https://www.skills.sh/muratcankoylan/agent-skills-for-context-engineering/filesystem-context) | offload log และเก็บผลเต็มให้เรียกอ่านได้ | 310 installs; repo 18.2K stars; First Seen 20 ม.ค. 2026 | กลุ่มทดลอง หรือเริ่มจากแม่แบบไฟล์สั้น ๆ ก่อน |
| [spec-driven-development](https://www.skills.sh/addyosmani/agent-skills/spec-driven-development) | Leader กำหนดสเปกเมื่อ feature มีความซับซ้อน | 58.1K installs; repo ราว 107K stars; First Seen 16 ก.พ. 2026 | ควรเริ่ม; ข้าม workflow เต็มสำหรับ typo/แก้เล็ก |
| [code-review-and-quality](https://www.skills.sh/addyosmani/agent-skills/code-review-and-quality) | Reviewer ตรวจคุณภาพก่อนส่งมอบ | 66.3K installs; repo ราว 108K stars; First Seen 16 ก.พ. 2026 | ควรเริ่มและเปิดเฉพาะขั้น review |
| [webapp-testing](https://www.skills.sh/anthropics/skills/webapp-testing) | Verifier ใช้ Playwright และ helper ตรวจเว็บ | 180.5K installs; official Anthropic repo ราว 182K stars; First Seen 19 ม.ค. 2026 | ใช้เมื่อทำเว็บและ runtime มี dependencies |
| [agent-browser](https://www.skills.sh/vercel-labs/agent-browser/agent-browser) | browser research และการตรวจ UI ด้วย snapshot | 1.2M installs; Vercel repo 44.1K stars; First Seen 19 ม.ค. 2026 | เพิ่มเมื่อจำเป็น; Orca embedded browser ใช้ Orca CLI ตามคู่มือ ไม่ต้องติดตั้งซ้ำเพื่อทำหน้าที่เดียวกัน |
| [content-strategy](https://www.skills.sh/coreyhaines31/marketingskills/content-strategy) | Researcher/Leader วางหัวข้อและกลุ่มเป้าหมาย | 158.8K installs; repo 55.3K stars; First Seen 26 ม.ค. 2026 | เปิดเฉพาะ content/affiliate project |
| [seo-audit](https://www.skills.sh/coreyhaines31/marketingskills/seo-audit) | Verifier ตรวจเว็บ affiliate/content | directory รวมแสดงราว 230K installs; repo เดียวกับ content-strategy | เพิ่มเมื่อมีเว็บไซต์และข้อมูลจริงให้ audit |

First Seen คือวัน directory พบรายการ ไม่ใช่หลักฐานวันสร้าง skill ทั้งหมด ผลตรวจอัตโนมัติของบางรายการมี Warn จึงควรอ่าน scripts, permission และ dependencies ของรุ่นที่จะติดตั้ง แล้ว pin commit/version ที่ตรวจแล้ว

เริ่มต้นเลือกเพียง Orca guides, spec, review และ testing ที่ตรงงาน แล้วค่อยทดลอง context skills ไม่ติดตั้งชุดใหญ่หลายชุดที่สั่งงานซ้ำกัน ประโยชน์ของ skill ด้านคุณภาพมักมาจากลดการทำผิด/แก้ซ้ำ ไม่ใช่ทำให้ทุกครั้งใช้ token น้อยลง

### ตัวอย่างคำสั่งติดตั้งที่เลือกเป็นรายตัว

คำสั่งต่อไปนี้เป็นข้อเสนอ ยังไม่ได้รัน การติดตั้งหลาย account/profile ต้องตรวจ directory ที่ client แต่ละตัวค้นหา อย่าสมมติว่าติดตั้งครั้งเดียวจะเห็นทุกบัญชี

```powershell
npx skills add addyosmani/agent-skills --skill spec-driven-development
npx skills add addyosmani/agent-skills --skill code-review-and-quality
npx skills add anthropics/skills --skill webapp-testing
npx skills add muratcankoylan/Agent-Skills-for-Context-Engineering --skill context-optimization
npx skills add muratcankoylan/Agent-Skills-for-Context-Engineering --skill context-compression
npx skills add coreyhaines31/marketingskills --skill content-strategy
```

Repo ของ Addy ระบุว่าติดตั้งเป็นราย skill อาจไม่พา repo-level references มาด้วย ต้องตรวจไฟล์อ้างอิงก่อนใช้งานจริง: [คำอธิบายจากผู้ดูแล](https://github.com/addyosmani/agent-skills)

### เครื่องมือเพิ่มเติมที่น่าทดลอง

[RTK](https://github.com/rtk-ai/rtk) เป็น CLI สำหรับลดข้อความผลคำสั่งที่ agent ต้องอ่าน และมีวิธีติดตั้ง Windows ตัวเลข 60–90% ที่โครงการกล่าวถึงเป็น output ของคำสั่งทั่วไป ไม่ใช่โควตาหรือค่าใช้จ่ายรวมลดเท่ากัน แนะนำเริ่มทดลองส่วนกรอง output เฉพาะงานและตรวจว่าเก็บ exit code/หลักฐานครบ; API proxy ไม่จำเป็นต่อแบบ subscription นี้

ข้อมูลเสริมหลังตรวจเครื่องมือเพิ่ม: [JetBrains ทดสอบ RTK v0.43.0 กับ Claude Code/Sonnet 5](https://blog.jetbrains.com/ai/2026/07/rtk-claude-code-token-savings/) แล้วไม่พบต้นทุนรวมลดลงในชุดงานนั้น จึงจัด RTK เป็นตัวทดลองตาม workload แทนการเปิดเป็นค่าเริ่มต้นทั้งทีม ดู [เปรียบเทียบ RTK, Headroom, Serena, Ponytail และ Caveman](token-tools-comparison.th.md) สำหรับข้อเสนอที่ปรับแล้ว

## รองรับงานนอก software

ใช้ทีมแกนเดิมแล้วเปลี่ยน domain skill, tool และเกณฑ์สำเร็จ ไม่ต้องสร้าง permanent agent ตามทุกอาชีพ

| งาน | สายงานและหลักฐาน |
|---|---|
| Software | repo discovery → contract → implement → unit/integration/UI checks → review → release → monitor |
| Affiliate | audience/product research → ตรวจข้อมูลสินค้าและเงื่อนไขปัจจุบัน → brief → comparison/content → claim/link checks → เผยแพร่ตามสิทธิ์ → วัด click/conversion |
| Social content | audience + angle → fact sheet → scripts/captions/visual brief หลายชิ้น → ตรวจ claims/brand/format → schedule ตามสิทธิ์ → วัด retention/engagement |
| Game | core loop + prototype scope → mechanics/UI/assets แยกงาน → playtest/performance/balance → build → วัดข้อผิดพลาดและพฤติกรรมผู้เล่น |
| Research/เอกสาร/ข้อมูล | ระบุคำถาม → แบ่งแหล่งข้อมูล → วิเคราะห์ → ตรวจ source/formula/layout → ส่งมอบ artifact |

งาน visual/audio/game engine อาจต้อง tool/model เฉพาะและค่าใช้จ่ายแยกจาก text subscription ให้ Leader ตรวจ capability ที่มีจริงก่อนรับปากเรื่องผลลัพธ์ ติดตั้ง domain pack หลังเลือก stack/engine/channel เพื่อไม่เพิ่มคลังที่ยังไม่ได้ใช้

## แผนเริ่มใช้งานและวิธีวัดผล

1. เริ่มหนึ่งบัญชีที่เข้าถึง Sol/Opus และโมเดล worker ได้ ยืนยันโมเดลที่รันจริง และเปิด worker พร้อมกัน 2 ตัว
2. ใช้ task contract จากแม่แบบด้านล่างกับงานอ่านและ feature จริง ทดลองแบ่ง scope/ไฟล์ให้ไม่ซ้ำ
3. เมื่อการติดตามงานและหลักฐานทำงานดี ค่อยเพิ่มเป็น 3–4 worker และเพิ่ม provider หรือบัญชีอื่นที่ตรวจ identity แล้ว
4. ทดลอง skill เพิ่มทีละชุด และเก็บต้นทุนจากการอ่าน skill ด้วย ไม่วัดเฉพาะ output ที่สั้นลง
5. เลือกงานตัวอย่าง 6–10 งานจาก repo/content ที่คุณทำจริง เทียบหนึ่ง agent กับทีมขนาดเล็กบน input และเงื่อนไขสำเร็จเดียวกัน หากต้องเทียบคุณภาพอย่างจริงจังให้ทำซ้ำเพราะโมเดลมีความแปรปรวน
6. เก็บเวลาถึงผลงานที่ผ่านตรวจ, สัดส่วนผ่านครั้งแรก, จำนวนแก้ซ้ำ, total usage ที่อ่านได้ และการใช้ quota ต่อช่วงเวลา; เปรียบเทียบภายใน plan เดียวกัน หาก usage ละเอียดอ่านไม่ได้ให้ระบุว่าไม่มีข้อมูล
7. ลบหรือ archive กฎ/skill ที่ไม่ช่วยให้ผลงานผ่านเร็วขึ้นหรือดีขึ้น ตรวจใหม่เมื่อเปลี่ยนโมเดลหรือ Orca version

ไฟล์ประกอบ: [Leader policy draft](leader-policy.draft.md), [task และ result templates](task-templates.md), [Orca capability notes](orca-capabilities.md)
