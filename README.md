# SawULearn — Mini Project

เว็บช่วยฝึกซออู้ผ่านกล้องและไมโครโฟน พร้อม **โมเดลล่าสุดที่ฝึกจาก expert01 + expert02 ทั้ง 4 ตัว** และ Jupyter Notebook แยกการฝึก, Validation และ Test

## เปิดใช้งานหลังโคลน — Windows

ติดตั้ง **Git และ Python 3.12 แบบ 64-bit** พร้อม Python Launcher (`py`) ก่อน การติดตั้งครั้งแรกต้องใช้เน็ตดาวน์โหลดแพ็กเกจ ไม่ต้องติดตั้ง Node.js เพื่อเปิดเว็บที่ build ไว้แล้ว

```powershell
git clone https://github.com/Thitapa5565/SawULearn_miniproject.git
cd SawULearn_miniproject
powershell -ExecutionPolicy Bypass -File .\setup.ps1
powershell -ExecutionPolicy Bypass -File .\web_app\start.ps1
```

เปิด **http://127.0.0.1:8000/#practice** ใน Chrome หรือ Edge อนุญาตกล้องและไมโครโฟน เปิด Terminal ของเซิร์ฟเวอร์ทิ้งไว้ กด Ctrl+C เพื่อหยุด

`setup.ps1` สร้าง `.venv` ในโฟลเดอร์ที่โคลน ติดตั้งทั้งเว็บและ Notebook แล้วตรวจ SHA256 ของโมเดลกับชุด Feature ใช้ `constraints.txt` ล็อกรุ่นแพ็กเกจตาม environment ที่ทดสอบใหม่ หากต้องการเฉพาะเว็บให้รัน `setup.ps1 -WebOnly` แทน

กล้องและการเทียบเสียงทำงานในเครื่อง โมเดล MediaPipe อยู่ใน repository แล้ว ไม่ต้องโหลดโมเดลเพิ่มขณะฝึก **วิดีโอบทเรียน DLTV ต้องใช้เน็ต** ข้อมูลประวัติฝึกเก็บในเบราว์เซอร์เครื่องนั้น และดาวน์โหลดเป็น JSON ได้

## วิธีสาธิต

1. กดเริ่มฝึก ดูภาพท่านั่งตัวอย่าง เลือกโน้ต และกดเปิดไมค์ก่อนถอยไปนั่ง
2. เปิดกล้อง ให้เห็นศีรษะ ไหล่ สะโพก และมือขวา รอคอและไหล่ผ่านเกณฑ์
3. ยกนิ้วโป้งฝั่งซ้ายของจอค้างประมาณ 2 วินาที หรือใช้ปุ่มยืนยัน
4. ลดนิ้วโป้งลงจับคันชัก ดึงไปทางขวาของผู้เล่นจนสุดช่วงที่สบาย มีเวลาเตรียม 10 วินาที แล้วค้างท่าให้ตรวจประมาณ 2 วินาที
5. เริ่มสีซอ ดูผลก้มหน้า/ไหล่เอียงและคำเตือนปรับองศาการสี ผลจับเริ่มต้นคงอยู่ใต้หลอดคีย์ กดตรวจใหม่เมื่อเปลี่ยนท่าจับ
6. ดูความถี่และหลอดคีย์: ต่ำไป / ตรงคีย์ / สูงไป โดยตรงคีย์เมื่อคลาดเคลื่อนไม่เกิน ±5 Hz

ก้มหน้าและไหล่เอียงแสดงคำเตือนพร้อมกันได้ แต่ชุด Test รอบนี้ไม่มีเฟรมจริงที่ผิดทั้งสองอาการพร้อมกัน จึงยังไม่มีผลวัดความไวของกรณีร่วม

## โมเดลที่ใช้

| งาน | โมเดล | Feature | พารามิเตอร์หลัก | ขนาดไฟล์ final |
| --- | --- | ---: | --- | ---: |
| ก้มหน้า | Random Forest | 10 | 150 ต้น, depth ไม่จำกัด, leaf 2 | 934,434 bytes |
| ไหล่เอียง | Random Forest | 10 | 150 ต้น, depth 3, leaf 2 | 231,895 bytes |
| จับพอดี/สูง/ต่ำตอนเริ่ม | Random Forest | 2 | 150 ต้น, depth 6, leaf 5 | 378,401 bytes |
| มุมผิดหรือสีลอย | Decision Tree | 4 | depth 3, leaf 10 | 3,461 bytes |

รวมโมเดล final ทั้ง 4 ตัว **1,548,191 bytes ≈ 1.55 MB** ไฟล์ต้นฉบับและ SHA256 ไม่เปลี่ยนจากรุ่นที่เปิดใช้ในเว็บเดิม

MediaPipe Pose Landmarker Heavy และ Hand Landmarker เป็นโมเดลสำเร็จรูปสำหรับหาจุดร่างกาย/นิ้ว นับแยกจาก 4 ตัวที่ฝึกเอง การเทียบเสียงใช้ **YIN** และ Web Audio ไม่ใช่โมเดลเสียงที่ฝึกเอง

## เปิด Notebook ล่าสุด

หลัง `setup.ps1` เปิดใน VS Code พร้อม Python/Jupyter extensions แล้วเลือก interpreter **`.venv/Scripts/python.exe`** หรือใช้ JupyterLab:

```powershell
.\.venv\Scripts\python.exe -m jupyterlab
```

เปิดโฟลเดอร์ `training/notebooks/15_combined_experts/` ตามลำดับ:

1. **01_train_combined_experts.ipynb** — ตรวจ Label/Feature, grouped CV, เปรียบเทียบ Decision Tree กับ Random Forest, เลือกด้วย Validation, fit Train+Val, กราฟต้นไม้และความสำคัญ Feature
2. **02_validation_results.ipynb** — คะแนน Train/Validation, confusion matrix, precision/recall/F1, แยกรายคน/คลิป และตัวอย่างผิด
3. **03_test_results.ipynb** — ผล Test ขั้นสุดท้าย, Coverage, คะแนนรายคลาส/คน/คลิป และ clip bootstrap

**มีผลรัน ตาราง และกราฟบันทึกใน Notebook แล้ว** ค่าเริ่มต้น `TRAIN_NEW=False` ใช้โมเดลและผลค้นเดิม จึงไม่ฝึกใหม่เมื่อ Run All ถ้าต้องการฝึกรอบใหม่ให้ตั้ง `TRAIN_NEW=True` ในเล่ม 01 แล้วนำค่า RUN ใหม่ไปใส่เล่ม 02–03 การฝึกใหม่ไม่เปลี่ยนโมเดลเว็บไซต์เอง

## Dataset และการประเมิน

ต้นทางมีผู้เล่น 2 คน / 64 คลิป / 2,082 เฟรม แบ่งตามคลิป Train 38 / Validation 13 / Test 13 เพื่อไม่ให้เฟรมของคลิปเดียวกันข้ามชุด จำนวนเฟรมของแต่ละงานไม่เท่ากัน และบางเฟรมใช้ในหลายงาน ห้ามบวกจำนวนแถวทุกงานเป็นจำนวนรูปจริง

repository รวม **CSV Feature ที่ตรวจ Label แล้ว, audit แถวที่จุดไม่ครบ, manifest และ SHA256** เพียงพอสำหรับรันการฝึก/ประเมินซ้ำ ไม่รวมคลิปต้นฉบับทั้งหมดหรือขั้นสกัดเฟรมซ้ำ มีภาพตัวอย่างท่านั่งและภาพผิดบางภาพสำหรับอธิบายผล Notebook

เลือกพารามิเตอร์ด้วย grouped CV ภายใน Train แล้วใช้ Validation เลือกโมเดลแต่ละงาน ล็อกตัวเลือกก่อน fit Train+Val และเปิด Test ขั้นสุดท้าย

| งาน | Test Accuracy รวมเฟรมจุดไม่ครบ | Test Macro F1 แบบให้น้ำหนักคลิปเท่ากัน |
| --- | ---: | ---: |
| ก้มหน้า | 84.7% | 0.678 |
| ไหล่เอียง | 84.0% | 0.783 |
| จับสูง/ต่ำตอนเริ่ม | 65.7% | 0.804 |
| มุมผิดหรือสีลอย | 55.2% | 0.631 |

ค่า Accuracy เฉลี่ยแบบให้น้ำหนัก 4 งานเท่ากัน **72.4%** ไม่ใช่คะแนนรวมจากเฟรมทุกงานที่นับเป็นอิสระ และ Macro F1 ไม่ใช่ Accuracy ผลละเอียดอยู่ใน Notebook และ `training/reports/combined_experts_20261007_211339_512861/`

ข้อจำกัด: ผู้เล่นทั้งสองมีคลิปใน Train จึงยังไม่ใช่การทดสอบคนใหม่ทั้งคน การจับเริ่มต้นต้องทำตามท่าขวาสุดที่กำหนด ส่วนคำเตือนแนวสีใช้มือ/ลำตัวเป็นตัวแทน ไม่ได้วัดมุมคันชักหรือระยะถึงหย่องโดยตรง ผล Test ของแนวสีรวมเฟรมที่จุดไม่ครบตรวจพบภาพผิด 12/40 เฟรม ไม่ควรตีความช่องสีเขียวเป็นการรับรองท่าถูกทุกกรณี ±5 Hz เป็นเกณฑ์ยอมรับของหน้าจอ ไม่ใช่ผลวัดความคลาดเคลื่อนของระบบเสียง

## โครงสร้าง

```text
setup.ps1                         ติดตั้งและตรวจความพร้อม
requirements*.txt                แพ็กเกจเว็บ / Notebook / ทดสอบ
web_app/src/                     React UI รุ่นปัจจุบัน
web_app/backend/                 FastAPI และ geometry/inference
web_app/dist/                    เว็บ build แล้ว เปิดใช้ได้ทันทีหลังติดตั้ง Python
training/models/                 โมเดลล่าสุด + MediaPipe
training/data/processed/          Feature และ audit สำหรับฝึกซ้ำ
training/notebooks/15_combined_experts/
training/reports/                 ผล CV / Validation / Test และกราฟ
scripts/                         ตรวจติดตั้งและรันตรวจ Notebook
tests/                           ทดสอบโมเดลและเว็บ
docs/                            รายละเอียด Feature และที่มาของชุดส่ง
```

## แก้หน้าเว็บและทดสอบ

ถ้าจะแก้ UI ให้ติดตั้ง Node.js 22 แล้วรัน:

```powershell
cd web_app
npm.cmd ci
npm.cmd test
npm.cmd run build
cd ..
```

ทดสอบ Python/API และ Notebook (ต้องใช้เน็ตเฉพาะตอนติดตั้งแพ็กเกจ):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/verify_notebooks.py
```

ใช้ `scripts/verify_notebooks.py` เมื่อต้องการตรวจ Run All ทั้ง 3 เล่ม สคริปต์ไม่เปลี่ยนโมเดลที่เว็บเปิดใช้อยู่ เก็บผลตรวจใน `.runtime/` ซึ่งไม่ติด Git

ผลตรวจชุดส่งจริงอยู่ใน `docs/verification.json` ตรวจไฟล์หลังโคลนด้วย `python scripts/verify_manifest.py` ก่อนแก้ไฟล์หรือ Run All เพื่อเทียบกับ `submission_manifest.json` แผ่นพับ/รายงาน Word ส่วนตัวและคลิปต้นฉบับเต็มไม่ได้รวมใน repository นี้
