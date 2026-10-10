# เครื่องมือ โมเดล และสื่ออ้างอิง

- MediaPipe Pose Landmarker Heavy float16 v1 และ Hand Landmarker float16 v1 ใช้หาจุดร่างกายและนิ้วก่อนคำนวณ Feature ไม่ใช่โมเดลจำแนกท่าที่ผู้จัดทำฝึกเอง ดู [Pose Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker) และ [Hand Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker) รวมถึงเงื่อนไขของต้นทาง
- โค้ด MediaPipe มี [Apache 2.0 license](https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE)
- ไฟล์ Pose แนบจาก `https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task` และไฟล์ Hand จาก `https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task` ค่า SHA256 ของไฟล์จริงอยู่ใน `submission_manifest.json`
- scikit-learn ใช้ Decision Tree / Random Forest และตัวชี้วัด ดู [เอกสารต้นทาง](https://scikit-learn.org/stable/)
- React, Vite, FastAPI, Uvicorn, NumPy, SciPy, pandas, Matplotlib, Pillow, Jupyter และ OpenCV เป็น dependencies ของระบบ เงื่อนไขใช้งานอยู่ในแพ็กเกจของแต่ละโครงการ
- ฟอนต์จาก Fontsource (Noto Sans Thai, Noto Serif Thai, Inter) และ Lucide icons ถูก build รวมในเว็บ ดู license ที่แนบในแพ็กเกจต้นทางของ `web_app/package-lock.json`
- การเทียบเสียงประยุกต์ YIN ตาม [de Cheveigné & Kawahara, 2002](https://pubmed.ncbi.nlm.nih.gov/12002874/) ทำงานผ่าน Web Audio ในเบราว์เซอร์ ไม่มีการฝึกโมเดลเสียง
- บทเรียนอ้างอิง [DLTV: การไล่นิ้ว การกดสาย การใช้คันชักซออู้](https://dltv.ac.th/teachplan/episode/58966) ระบบเปิดวิดีโอจากต้นทาง ไม่ได้แนบสำเนาคลิป DLTV ลง repository
