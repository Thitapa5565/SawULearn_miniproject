"""Build and execute three teaching notebooks for the combined expert dataset."""
from __future__ import annotations

import argparse
from pathlib import Path
import textwrap

import nbformat as nbf
from nbclient import NotebookClient

from . import combined_experts as ce

NB_DIR = ce.ROOT/'notebooks/15_combined_experts'
TREE_GRID = {'max_depth':[2,3,4,6], 'min_samples_leaf':[2,5,10]}
FOREST_GRID = {'n_estimators':[150], 'max_depth':[3,6,None],
               'min_samples_leaf':[2,5], 'max_features':['sqrt',1.0]}


def md(source):
    return nbf.v4.new_markdown_cell(textwrap.dedent(source).strip())


def code(source):
    return nbf.v4.new_code_cell(textwrap.dedent(source).strip())


def notebook(cells):
    nb = nbf.v4.new_notebook(cells=cells)
    nb.metadata.kernelspec = {'name':'sawuai','language':'python','display_name':'Python (SawUAI .venv)'}
    return nb


def setup_cell():
    return code('''
        from pathlib import Path
        import sys, json
        PROJECT = next(p for p in [Path.cwd(), *Path.cwd().parents]
                       if (p/'training/src/training/combined_experts.py').exists())
        if str(PROJECT/'training') not in sys.path:
            sys.path.insert(0, str(PROJECT/'training'))
        import joblib
        import numpy as np
        import pandas as pd
        import matplotlib.pyplot as plt
        from IPython.display import display, Markdown, Image
        from src.training import combined_experts as ce
        ce.setup_plots()
        WEB_BEFORE = ce.web_fingerprints()
        pd.set_option('display.max_columns', 25)
        pd.set_option('display.max_colwidth', 100)
        print('Python:', sys.executable)
        print('Training directory:', ce.ROOT)
        print('scikit-learn:', ce.sklearn.__version__)
    ''')


def training_book(run):
    cells = [
        md('''
        # 01 · ฝึกโมเดลจาก expert01 + expert02
        เล่มนี้อธิบายและรันการฝึกทีละขั้น ส่วนรายละเอียดคะแนนอยู่ใน
        **02_validation_results.ipynb** และ **03_test_results.ipynb**

        มี 4 ตัวจำแนก: ก้มหน้า, ไหล่เอียง, จับสูง/ต่ำ/พอดี และควรปรับองศาการสี
        สองอาการท่านั่งแยกโมเดลจึงทำนายเป็น 1 พร้อมกันได้
        งานคันชักใช้ท่าร่างกายเป็นตัวแทน ไม่ได้วัดนิ้ว มุมคันชัก หรือระยะหย่องโดยตรง

        ขั้นตอน: ตรวจข้อมูล → ดู label/feature → TRAIN CV แยกคลิป → shortlist แต่ละครอบครัว →
        เลือกด้วย VAL → ล็อกตัวเลือก → fit TRAIN+VAL → บันทึกไฟล์

        **เปิด kernel `Python (SawUAI .venv)` แล้ว Run All** ค่าเริ่มต้นเปิดผลรอบนี้ซ้ำได้
        ถ้าปรับพารามิเตอร์ให้ตั้ง `TRAIN_NEW=True` เพื่อบันทึกรอบใหม่ โดยยังไม่เปลี่ยนโมเดลเว็บ
        ''')]
    cells += [md('## 1.1 · โหลดเครื่องมือและหาโฟลเดอร์'),setup_cell()]
    cells += [md('''
        ## 1.2 · ตั้งค่าการทดลอง
        `max_depth` จำกัดความลึก, `min_samples_leaf` กำหนดเฟรมขั้นต่ำต่อใบ,
        `n_estimators` จำนวนต้นไม้ใน Forest, `max_features` จำนวน feature ที่ให้ลองในแต่ละการแบ่ง
        ค้น 24 แบบของ Tree + 24 แบบของ Forest รวมโหมดน้ำหนักสองแบบแล้ว
        งานจับเริ่มต้นเปรียบเทียบ feature 2 ตัวกับ 4 ตัวด้วย TRAIN CV
        ทั้งหมดเป็นการค้นในขอบเขตที่กำหนด ไม่ใช่รับประกันดีที่สุดในทุกค่าที่เป็นไปได้
        '''),code(f'''
        SEED = 42
        CV_FOLDS = 3
        N_JOBS = 2
        TREE_GRID = {TREE_GRID!r}
        FOREST_GRID = {FOREST_GRID!r}
        TRAIN_NEW = False
        RUN = {run!r}
        print('Saved run:', RUN)
        ''')]
    cells += [md('''
        ## 2.1 · ตรวจความครบและป้องกันข้อมูลรั่ว
        ตรวจ SHA256 ของ CSV, label ที่ตรวจโดยคน และ clip/frame/video hash ไม่ซ้ำข้าม split
        ขั้นนี้อ่านเฉพาะข้อมูลระบุตัวตนของ test เพื่อตรวจ split ไม่เปิด feature/คำตอบ test เพื่อเลือกโมเดล
        '''),code('''
        summary, manifests = ce.verify_prepared_data()
        display(pd.DataFrame([{
            'dataset': name, 'reviewed': m['reviewed_frames'],
            'usable': m['usable_frames'], 'excluded_features': m['unusable_frames'],
            'train': m['splits']['train']['frames'], 'val': m['splits']['val']['frames'],
            'test_reserved': m['splits']['test']['frames']
        } for name,m in manifests.items()]))
        print('Source:', summary['source_clips'], 'clips /', summary['physical_frames'], 'physical frames')
        print('Counts across tasks overlap; do not add them as unique photos.')
        ''')]
    cells += [md('''
        ## 2.2 · เปิดพื้นที่บันทึกรอบนี้
        ทุก run มีโฟลเดอร์ models และ reports ของตนเอง และ snapshot ของโมเดลเว็บ
        ค่า `TRAIN_NEW=False` โหลดรอบที่ระบุ หาก True จะสร้าง run ใหม่ก่อนฝึก
        '''),code('''
        if TRAIN_NEW:
            RUN, REPORT, MODEL_DIR, record = ce.new_run(
                SEED, CV_FOLDS, TREE_GRID, FOREST_GRID,
                ce.web_fingerprints(), summary, manifests)
        else:
            REPORT = ce.ROOT/'reports'/RUN
            MODEL_DIR = ce.ROOT/'models'/RUN
            record = ce.read_json(REPORT/'training_record.json')
            assert record['dataset_sha256'] == summary['dataset_sha256']
            assert (SEED,CV_FOLDS,TREE_GRID,FOREST_GRID) == (
                record['seed'],record['cv_folds'],record['tree_grid'],record['forest_grid']), \
                'Configuration changed: set TRAIN_NEW=True'
        print('Run:', RUN)
        print('Report:', REPORT)
        print('Models:', MODEL_DIR)
        ''')]
    cells += [md('''
        ## 3.1 · Label และ Feature ของแต่ละงาน
        `0/1` หมายถึงไม่พบ/พบอาการ ก้มหน้าและไหล่เอียงเป็นอิสระกัน
        `none/grip_too_high/grip_too_low` คือจับพอดี/สูง/ต่ำ
        `target_bow_angle_wrong=1` รวมมุมผิดหรือสีลอยตาม label ที่คนตรวจ
        Feature มาจากสูตรใน `posture_features.py` และ `torso_hand_proxy.py` ไม่ใช้ชื่อไฟล์เป็นตัวทำนาย
        '''),code('''
        display(pd.DataFrame([{
            'task': key, 'meaning': spec['title'], 'label_column': spec['target'],
            'classes': ', '.join(spec['labels']),
            'feature_sets': json.dumps(spec['features'], ensure_ascii=False)
        } for key,spec in ce.TASKS.items()]))
        ''')]
    cells += [md('''
        ## 3.2 · โหลดเฉพาะ TRAIN และ VAL
        หนึ่งแถวคือหนึ่งเฟรมพร้อม feature และ label แต่เฟรมในคลิปเดียวกันมีความสัมพันธ์กัน
        จึงประเมินหลักด้วยน้ำหนักรวมต่อคลิปเท่ากัน ไม่ให้คลิปยาวครองคะแนน
        '''),code('''
        train_data = {task: ce.load_split(task,'train') for task in ce.TASKS}
        val_data = {task: ce.load_split(task,'val') for task in ce.TASKS}
        for task in ce.TASKS:
            assert not set(train_data[task].clip_id) & set(val_data[task].clip_id)
        display(train_data['head_down'][ce.POSTURE + ['target_head_down','target_shoulder_tilt']].head())
        display(train_data['initial_grip'][ce.BODY + ['error_type']].head())
        ''')]
    cells += [md('## 3.3 · ตรวจจำนวนคำตอบรายคนและชุดข้อมูล'),code('''
        counts = []
        for task,spec in ce.TASKS.items():
            for split,df in [('train',train_data[task]),('val',val_data[task])]:
                grouped = df.groupby(['expert',spec['target']]).agg(frames=('frame_path','size'), clips=('clip_id','nunique'))
                for (expert,label), values in grouped.iterrows():
                    counts.append(dict(task=task,split=split,expert=expert,label=str(label),**values.to_dict()))
        counts_df = pd.DataFrame(counts)
        display(counts_df)
        counts_df.to_csv(REPORT/'train_val_class_counts.csv',index=False,encoding='utf-8-sig')
        ''')]
    cells += [md('''
        ## 3.4 · ดูภาพรวมการกระจายคำตอบและ feature
        ความแตกต่างระหว่างคนอาจเกิดจากขนาดตัว กล้อง หรือการตั้งท่า
        สีแสดงคำตอบจริง ไม่มีการตัดเฟรมที่คลาสซ้อนกันเพื่อเพิ่มคะแนน
        '''),code('''
        fig, axes = plt.subplots(1,4,figsize=(17,4))
        for ax,(task,spec) in zip(axes,ce.TASKS.items()):
            train_data[task][spec['target']].astype(str).value_counts().reindex(spec['labels'],fill_value=0).plot.bar(ax=ax,color='#21677c')
            ax.set(title=spec['title'],ylabel='TRAIN frames')
        fig.tight_layout(); fig.savefig(REPORT/'train_labels.png'); plt.show()
        grip = train_data['initial_grip']
        fig,axes = plt.subplots(1,2,figsize=(12,4))
        for ax,(expert,df) in zip(axes,grip.groupby('expert')):
            for label,g in df.groupby('error_type'):
                ax.scatter(g.bow_side_horizontal_ratio,g.wrist_height_body_ratio,label=label,alpha=.7)
            ax.set(title=expert,xlabel='bow_side_horizontal_ratio',ylabel='wrist_height_body_ratio'); ax.legend(fontsize=8)
        fig.tight_layout(); fig.savefig(REPORT/'grip_features_by_expert.png'); plt.show()
        ''')]
    cells += [md('''
        ## 4.1 · เข้าใจน้ำหนักที่ใช้ fit
        `clip_equal`: น้ำหนักแต่ละเฟรม = 1 / จำนวนเฟรมของคลิปนั้น แล้วปรับค่าเฉลี่ยให้เป็น 1
        `clip_class_balanced`: เริ่มจากน้ำหนักเท่ากันต่อคลิป แล้วปรับให้น้ำหนักรวมแต่ละคลาสเท่ากัน
        คำนวณน้ำหนักใหม่จากข้อมูลในแต่ละ fold เท่านั้น และเปรียบเทียบสองโหมดด้วย CV
        '''),code('''
        example = train_data['initial_grip'].copy()
        example['fit_weight'] = ce.fitting_weights(example,'error_type','clip_equal')
        display(example[['clip_id','error_type','fit_weight']].head(8))
        print('Equal clip totals:')
        display(example.groupby('clip_id').fit_weight.sum().head())
        ''')]
    cells += [md('''
        ## 4.2 · สร้าง Cross-validation ที่แยกทั้งคลิป
        StratifiedGroupKFold 3 folds ใช้ `clip_id` เป็นกลุ่ม
        แต่ละ fold ต้องมีทุกคลาสทั้งฝั่งฝึกและฝั่งตรวจ และไม่มีคลิปเดียวกันอยู่สองฝั่ง
        ตาราง fold เก็บไว้เพื่อให้ตรวจสอบย้อนกลับได้
        '''),code('''
        fold_indices = {task: ce.build_folds(df,task,CV_FOLDS,SEED) for task,df in train_data.items()}
        fold_record, fold_rows = {}, []
        for task,folds in fold_indices.items():
            df = train_data[task]
            fold_record[task] = []
            for number,(fit,held) in enumerate(folds,1):
                fit_clips = sorted(df.iloc[fit].clip_id.unique())
                held_clips = sorted(df.iloc[held].clip_id.unique())
                fold_record[task].append(dict(fold=number,fit_clips=fit_clips,held_clips=held_clips))
                fold_rows.append(dict(task=task,fold=number,fit_frames=len(fit),held_frames=len(held),fit_clips=len(fit_clips),held_clips=len(held_clips)))
        ce.save_json(REPORT/'cv_folds.json',fold_record)
        display(pd.DataFrame(fold_rows))
        ''')]
    cells += [md('''
        ## 4.3 · สร้างรายการค่าที่จะลอง
        Decision Tree เรียนกฎแบ่งข้อมูลเป็นเงื่อนไข ส่วน Random Forest รวมเสียงจากหลายต้นไม้
        ไม่ต้อง StandardScaler สำหรับสองอัลกอริทึมนี้
        '''),code('''
        candidates = ce.candidate_grid(TREE_GRID,FOREST_GRID)
        display(pd.DataFrame(candidates).head(8))
        print('Configurations per feature set:', len(candidates))
        print('Total configurations:', sum(len(s['features'])*len(candidates) for s in ce.TASKS.values()))
        ''')]
    for task in ce.TASKS:
        title = ce.TASKS[task]['title']
        cells += [md(f'''
            ## 5 · ค้นค่าของงาน {title} (`{task}`)
            ทุกตัวเลือก fit บนส่วน TRAIN ของ fold แล้วทำนายส่วนที่กันไว้
            รวมคำทำนาย out-of-fold เพื่อคำนวณ Macro F1 แบบคลิปมีน้ำหนักเท่ากัน
            ดูคะแนน CV และความแปรปรวนระหว่าง fold ไม่ใช้คะแนน train อย่างเดียว
            `ce.search_task` คือ loop fit/predict เดียวกันสำหรับทุกงาน อ่านโค้ดได้ใน `combined_experts.py`
            ''')]
        cells += [code(f'''
            search_path = REPORT/'cv_{task}.json'
            if not search_path.exists():
                trials = ce.search_task('{task}',train_data['{task}'],candidates,
                                        fold_indices['{task}'],SEED,N_JOBS)
                ce.save_json(search_path,trials)
            else:
                trials = ce.read_json(search_path)
            cv_table = ce.trial_table(trials)
            cv_table.to_csv(REPORT/'cv_{task}.csv',index=False,encoding='utf-8-sig')
            display(cv_table.head(12).round(4))
            fig,ax = plt.subplots(figsize=(11,4))
            top = cv_table.head(10).iloc[::-1]
            ax.barh(top.candidate_id,top.cv_f1,color='#21677c')
            ax.set(xlim=(0,1),xlabel='TRAIN CV · clip-balanced macro F1',title='{title}')
            fig.tight_layout(); fig.savefig(REPORT/'cv_{task}.png'); plt.show()
            ''')]
    cells += [md('''
        ## 6.1 · Shortlist และเลือกด้วย Validation
        ให้เฉพาะตัวที่ได้ TRAIN CV ดีที่สุดของแต่ละครอบครัวเข้ารอบ: 1 Tree และ 1 Forest ต่อหนึ่งงาน
        เลือกด้วย VAL clip-balanced macro F1; ถ้าเท่ากันดู CV และเลือก Tree เมื่อยังเท่ากัน
        มี Dummy ที่ทายคลาสส่วนใหญ่เป็นฐานเปรียบเทียบ
        รายละเอียด confusion matrix/รายคนอยู่เล่ม 02 และไม่มี TEST ในการเลือกนี้
        '''),code('''
        selection_path = REPORT/'selection.json'
        if not selection_path.exists():
            selection = {}
            for task in ce.TASKS:
                trials = ce.read_json(REPORT/f'cv_{task}.json')
                finalists, fitted, best, dummy, baseline = ce.validate_shortlist(
                    task,train_data[task],val_data[task],trials,SEED,N_JOBS)
                candidate_dir = MODEL_DIR/'validation/candidates'
                candidate_dir.mkdir(exist_ok=True)
                for finalist in finalists:
                    ce.save_bundle(task,fitted[finalist['candidate_id']],finalist,
                                   train_data[task],['train'],candidate_dir/f"{finalist['candidate_id']}.joblib",RUN)
                ce.save_bundle(task,fitted[best['candidate_id']],best,train_data[task],
                               ['train'],MODEL_DIR/'validation'/f'{task}.joblib',RUN)
                dummy_features = next(iter(ce.TASKS[task]['features'].values()))
                joblib.dump(dict(model=dummy,feature_columns=dummy_features),MODEL_DIR/'validation'/f'{task}_dummy.joblib')
                selection[task] = dict(selected=best,finalists=finalists,dummy_val=baseline)
            ce.save_json(selection_path,selection)
        else:
            selection = ce.read_json(selection_path)
        validation_rows = []
        for task,entry in selection.items():
            for item in entry['finalists']:
                validation_rows.append(dict(task=task,family=item['family'],features=item['feature_set'],
                    parameters=json.dumps(item['params']),weight_mode=item['weight_mode'],
                    train_f1=item['train']['clip_balanced_macro_f1'],cv_f1=item['cv']['clip_balanced_macro_f1'],
                    val_f1=item['val']['clip_balanced_macro_f1'],
                    selected=item['candidate_id']==entry['selected']['candidate_id']))
        validation_table = pd.DataFrame(validation_rows)
        display(validation_table.round(4))
        validation_table.to_csv(REPORT/'validation_shortlist.csv',index=False,encoding='utf-8-sig')
        ''')]
    cells += [md('''
        ## 6.2 · ล็อกตัวเลือกก่อนเปิด TEST
        บันทึกชื่อผู้ชนะ พารามิเตอร์ feature และ SHA256 ของ selection
        ต่อจากนี้ TEST ใช้รายงานผลเท่านั้น หากเห็น test แล้วแก้ค่าและประเมินชุดเดิมซ้ำ ผลจะไม่ใช่ test ที่สดใหม่
        '''),code('''
        lock_path = REPORT/'selection_lock.json'
        selection_hash = ce.sha256(selection_path)
        if lock_path.exists():
            assert ce.read_json(lock_path)['selection_sha256'] == selection_hash
        else:
            ce.save_json(lock_path,dict(run=RUN,selection_sha256=selection_hash,
                locked_at=ce.datetime.now(ce.ZoneInfo('Asia/Bangkok')).isoformat(),test_used_for_selection=False,
                winners={task:entry['selected']['candidate_id'] for task,entry in selection.items()}))
        display(pd.DataFrame([dict(task=task,selected=e['selected']['candidate_id'],
            family=e['selected']['family'],features=e['selected']['feature_set'],
            params=json.dumps(e['selected']['params']),weight_mode=e['selected']['weight_mode'])
            for task,e in selection.items()]))
        ''')]
    cells += [md('''
        ## 7.1 · Fit รุ่นสุดท้ายด้วย TRAIN + VAL
        หลังเลือกค่าจบแล้ว รวม TRAIN+VAL เพื่อให้รุ่นสุดท้ายได้เรียนจากข้อมูลมากขึ้น
        เก็บรุ่นที่ fit TRAIN อย่างเดียวไว้สำหรับรายงาน VAL แยกต่างหาก
        ห้ามใช้รุ่นสุดท้ายมารายงาน VAL ว่าเป็นข้อมูลที่โมเดลไม่เคยเห็น
        '''),code('''
        final_bundles = {}
        for task,entry in selection.items():
            path = MODEL_DIR/'final'/f'{task}.joblib'
            if not path.exists():
                fit_df = pd.concat([train_data[task],val_data[task]],ignore_index=True)
                best = entry['selected']
                model = ce.fit_candidate(task,fit_df,best,SEED,N_JOBS)
                ce.save_bundle(task,model,best,fit_df,['train','val'],path,RUN)
            final_bundles[task] = joblib.load(path)
        display(pd.DataFrame([dict(task=task,fit_splits=b['fit_splits'],
            frames=b['fit_frames'],clips=b['fit_clips'],features=b['feature_columns'])
            for task,b in final_bundles.items()]))
        ''')]
    cells += [md('''
        ## 7.2 · ตรวจ Feature importance
        เป็นความสำคัญจากการแบ่งกิ่งของโมเดล ไม่ใช่หลักฐานเหตุและผล
        Feature ที่คล้ายกันอาจแบ่งความสำคัญกัน และค่าความลึก z เป็นเพียงการประมาณ
        ''')]
    for task in ce.TASKS:
        cells += [code(f'''
            bundle = final_bundles['{task}']
            fig,importance = ce.plot_importance(bundle,'{ce.TASKS[task]['title']} · final model')
            display(importance.round(4))
            fig.savefig(REPORT/'importance_{task}.png'); plt.show()
            importance.to_csv(REPORT/'importance_{task}.csv',index=False,encoding='utf-8-sig')
            ''')]
    cells += [md('''
        ## 7.3 · อ่านต้นไม้และกฎ
        แต่ละ node แสดงเงื่อนไข feature และค่าตัด หากเป็น Forest แสดงต้นแรกเป็นตัวอย่างเท่านั้น
        แสดงต้นไม้ถึงระดับ 3 เพื่ออ่านง่าย กฎเต็มของ Decision Tree บันทึกเป็นไฟล์ข้อความ
        ก้มหน้าและไหล่เอียงมีต้นไม้/Forest คนละชุด ไม่บังคับให้เลือกอาการเดียว
        ''')]
    for task in ce.TASKS:
        cells += [code(f'''
            bundle = final_bundles['{task}']
            fig = ce.plot_model_tree(bundle,'{ce.TASKS[task]['title']}')
            fig.savefig(REPORT/'tree_{task}.png',dpi=130); plt.show()
            ce.save_tree_rules(bundle,REPORT/'rules_{task}.txt')
            ''')]
    cells += [md('''
        ## 8.1 · บันทึกหลักฐานและยืนยันว่าเว็บยังใช้รุ่นเดิม
        Artifact ที่ได้ยังเป็นชุดสำหรับประเมิน ไม่ใช่การนำไปใช้ในเว็บ
        เก็บเวอร์ชัน sklearn, hash ข้อมูล/โค้ด/โมเดล, รายการ clip ใน CV และตัวเลือกที่ล็อกแล้ว
        การคาดการณ์ในรอบนี้เป็นคลาสตรงจากโมเดล ยังไม่ได้เพิ่ม guard ความไม่แน่ใจหรือ smoothing ของเว็บ
        '''),code('''
        record['tasks'] = {task:dict(selected=entry['selected'],
            validation_model_sha256=ce.sha256(MODEL_DIR/'validation'/f'{task}.joblib'),
            final_model_sha256=ce.sha256(MODEL_DIR/'final'/f'{task}.joblib'))
            for task,entry in selection.items()}
        record['source_hashes'] = record.get('source_hashes') or {
            'training_helpers':ce.sha256(ce.ROOT/'src/training/combined_experts.py'),
            'notebook_builder':ce.sha256(ce.ROOT/'src/training/build_combined_notebooks.py'),
            'posture_geometry':ce.sha256(ce.ROOT/'src/data/posture_features.py'),
            'body_geometry':ce.sha256(ce.ROOT/'src/data/torso_hand_proxy.py')}
        record['web_after_training'] = ce.web_fingerprints()
        assert WEB_BEFORE == record['web_after_training'], 'Deployed model changed'
        record['training_complete'] = True
        record['deployed'] = False
        ce.save_json(REPORT/'training_record.json',record)
        ce.save_json(MODEL_DIR/'summary.json',record)
        print('Training complete:', RUN)
        print('Web model unchanged: verified')
        print('Next: 02_validation_results.ipynb → 03_test_results.ipynb')
        ''')]
    cells += [md('''
        ## 8.2 · ข้อจำกัดที่ต้องอ่านก่อนใช้คะแนน
        - มีเพียงสองคน และแต่ละคนมีคลิปอยู่ทั้ง train/val/test จึงวัดคลิปที่กันไว้ของคนเดิม ไม่ใช่ความแม่นกับคนใหม่
        - ข้อมูล expert01 บาง split เคยใช้ในการทดลองก่อนหน้าแล้ว แม้ไม่มีการรั่วของคลิปในรอบนี้ test จึงไม่ใช่ข้อมูลใหม่ทั้งหมด
        - งานจับสูง–ต่ำตรวจเฉพาะท่าขวาสุดตอนเริ่ม ผลระหว่างการสีไม่อยู่ในขอบเขตการฝึกนี้
        - งานองศาการสีใช้ body proxy จึงอาจแยกผิดเมื่อมือ/ลำตัวมีท่าคล้ายกัน
        - คะแนนเฟรมที่ landmark ครบและคะแนนรวมเฟรมที่ landmark ไม่ครบแยกไว้ในเล่มประเมิน
        - การเปิด TEST มีจุดประสงค์รายงาน ไม่ใช้ปรับพารามิเตอร์อีกในรอบนี้
        ''')]
    return notebook(cells)


def evaluation_book(run, split):
    is_test = split == 'test'
    number, name = ('03','TEST') if is_test else ('02','VALIDATION')
    model_folder = 'final' if is_test else 'validation'
    cells = [md(f'''
        # {number} · ผล {name} แบบละเอียด · expert01 + expert02
        {'ใช้รุ่น final ที่ fit TRAIN+VAL แล้วทดสอบกับคลิป TEST ที่กันไว้ หลังล็อกตัวเลือก' if is_test else 'ใช้รุ่นที่ fit TRAIN เท่านั้น เพื่อดูผลบน VAL และเหตุผลการเลือกโมเดล'}
        เล่มนี้ประเมินอย่างเดียว ไม่ fit หรือเปลี่ยนพารามิเตอร์ และไม่เปลี่ยนโมเดลเว็บ

        แยก **usable** (landmark/feature ครบ) กับ **all reviewed** (รวมเฟรมที่ตรวจ landmark ไม่ได้)
        เฟรมที่ตรวจไม่ได้มีผล `__unavailable__` และนับเป็นทายไม่สำเร็จ ไม่เติมว่าท่าถูก
        คะแนนหลัก **clip-balanced Macro F1** ให้น้ำหนักรวมแต่ละคลิปเท่ากัน และเฉลี่ยทุกคลาสเท่ากัน
        ''')]
    cells += [md('## 1.1 · โหลดเครื่องมือ'),setup_cell(),md('## 1.2 · ระบุ run และยืนยันตัวเลือกที่ล็อกไว้'),code(f'''
        RUN = {run!r}
        REPORT = ce.ROOT/'reports'/RUN
        MODEL_DIR = ce.ROOT/'models'/RUN
        SPLIT = {split!r}
        MODEL_FOLDER = {model_folder!r}
        record = ce.read_json(REPORT/'training_record.json')
        lock = ce.read_json(REPORT/'selection_lock.json')
        assert lock['selection_sha256'] == ce.sha256(REPORT/'selection.json')
        assert lock['test_used_for_selection'] is False
        for task in ce.TASKS:
            expected = record['tasks'][task][{'final_model_sha256' if is_test else 'validation_model_sha256'!r}]
            assert ce.sha256(MODEL_DIR/MODEL_FOLDER/f'{{task}}.joblib') == expected
        print('Run:',RUN)
        print('Fit splits:', {'["train","val"]' if is_test else '["train"]'})
        print('Evaluation split:',SPLIT)
        ''')]
    cells += [md('''
        ## 2.1 · จำนวนภาพที่ตรวจได้และตรวจไม่ได้
        จำนวนแต่ละงานอาจซ้อนกันเพราะใช้ภาพเดียวกัน อย่ารวมเป็นจำนวนภาพต้นฉบับ
        Coverage คือจำนวนที่ feature ครบ / จำนวนเฟรมที่ผู้ตรวจเลือกสำหรับงานนั้น
        '''),code('''
        inventory = []
        for dataset in sorted({s['dataset'] for s in ce.TASKS.values()}):
            usable = pd.read_csv(ce.DATA/dataset/f'{SPLIT}.csv')
            audit = pd.read_csv(ce.DATA/dataset/f'{SPLIT}_audit.csv')
            inventory.append(dict(dataset=dataset,reviewed_frames=len(audit),usable_frames=len(usable),
                excluded_frames=len(audit)-len(usable),clips=audit.clip_id.nunique(),coverage=len(usable)/len(audit)))
        display(pd.DataFrame(inventory).round(4))
        ''')]
    cells += [md('''
        ## 2.2 · ความหมายคะแนน
        - **Accuracy:** สัดส่วนที่ทายถูก
        - **Precision:** เมื่อแจ้งว่าผิด มีคำตอบจริงผิดกี่ส่วน
        - **Recall:** จากภาพที่ผิดจริง ตรวจพบกี่ส่วน
        - **F1:** รวม Precision และ Recall; Macro F1 เฉลี่ยทุกคลาสเท่ากัน
        - **Clip-balanced:** น้ำหนักรวมต่อคลิปเท่ากัน ลดผลจากคลิปที่มีเฟรมมาก
        - **Support:** จำนวนเฟรมในตารางปกติ; ในตารางถ่วงน้ำหนักคือผลรวมน้ำหนัก ไม่ใช่จำนวนเฟรม
        Model support จาก predict_proba ยังไม่ใช่เปอร์เซ็นต์ความแม่นยำที่ปรับเทียบแล้ว
        ''')]
    cells += [md('## 3.1 · ทำนายและบันทึกผลทุกงาน'),code('''
        results, rows_by_task, bundles = {}, {}, {}
        for task in ce.TASKS:
            bundle = joblib.load(MODEL_DIR/MODEL_FOLDER/f'{task}.joblib')
            expected_fit = ['train','val'] if SPLIT=='test' else ['train']
            assert bundle['fit_splits'] == expected_fit
            result,rows = ce.evaluate_bundle(task,bundle,SPLIT,REPORT)
            results[task],rows_by_task[task],bundles[task] = result,rows,bundle
        scores = ce.result_table(results)
        display(scores.round(4))
        scores.to_csv(REPORT/SPLIT/'summary_scores.csv',index=False,encoding='utf-8-sig')
        ce.save_json(REPORT/SPLIT/'results.json',results)
        ''')]
    cells += [md('''
        ## 3.2 · เปรียบเทียบคะแนน usable กับคะแนนรวมทั้งหมด
        คะแนน usable บอกความสามารถตัวจำแนกเมื่อได้รับ feature ครบ
        คะแนน all reviewed รวมปัญหา landmark ของ pipeline ด้วย จึงอาจต่ำกว่า
        ตารางหลักไม่ซ่อนเฟรมที่โมเดลทายผิดหรือ landmark ไม่ครบ
        '''),code('''
        fig,axes = plt.subplots(1,2,figsize=(13,4))
        x = np.arange(len(scores)); width=.35
        for ax,cols,title in [
            (axes[0],['balanced_f1_usable','balanced_f1_all'],'Macro F1 · equal clip weight'),
            (axes[1],['balanced_accuracy_all','balanced_coverage'],'Accuracy / coverage · all reviewed')]:
            for offset,col in enumerate(cols):
                bars=ax.bar(x+(offset-.5)*width,scores[col],width,label=col)
                ax.bar_label(bars,fmt='%.3f',fontsize=8)
            ax.set_xticks(x,scores.task,rotation=15); ax.set(ylim=(0,1.12),title=title); ax.legend(fontsize=8)
        fig.tight_layout(); fig.savefig(REPORT/SPLIT/'scores.png'); plt.show()
        ''')]
    if not is_test:
        cells += [md('''
            ## 4.1 · Tree / Forest / Dummy และเหตุผลที่เลือก
            Tree/Forest ฝึกจาก TRAIN เท่านั้น; Dummy ทายคลาสส่วนใหญ่จาก TRAIN
            ตารางนี้เป็นคะแนน usable ที่ใช้เลือกครอบครัวโมเดล พร้อมช่องว่าง train–val
            หาก train สูงแต่ val ต่ำ อาจ overfit หรือข้อมูลคน/คลิปต่างกัน
            '''),code('''
            selection = ce.read_json(REPORT/'selection.json')
            compare = []
            for task,entry in selection.items():
                for candidate in entry['finalists']:
                    candidate_bundle = joblib.load(MODEL_DIR/'validation/candidates'/f"{candidate['candidate_id']}.joblib")
                    ce.evaluate_bundle(task,candidate_bundle,'val',REPORT,tag=candidate['family'])
                    compare.append(dict(task=ce.TASKS[task]['title'],family=candidate['family'],
                        selected=candidate['candidate_id']==entry['selected']['candidate_id'],
                        train_f1=candidate['train']['clip_balanced_macro_f1'],cv_f1=candidate['cv']['clip_balanced_macro_f1'],
                        val_f1=candidate['val']['clip_balanced_macro_f1'],
                        gap=candidate['train']['clip_balanced_macro_f1']-candidate['val']['clip_balanced_macro_f1']))
                compare.append(dict(task=ce.TASKS[task]['title'],family='dummy_majority',selected=False,
                    val_f1=entry['dummy_val']['clip_balanced_macro_f1']))
            comparison = pd.DataFrame(compare)
            display(comparison.round(4))
            comparison.to_csv(REPORT/'val/model_comparison.csv',index=False,encoding='utf-8-sig')
            fig,axes=plt.subplots(1,4,figsize=(17,4))
            for ax,(title,df) in zip(axes,comparison.groupby('task',sort=False)):
                ax.bar(df.family,df.val_f1,color=['#21677c','#e59437','#a9a9a9'])
                ax.set(title=title,ylim=(0,1),ylabel='VAL usable · balanced F1'); ax.tick_params(axis='x',rotation=35)
            fig.tight_layout(); fig.savefig(REPORT/'val/comparison.png'); plt.show()
            ''')]
    else:
        cells += [md('''
            ## 4.1 · เทียบกับ Dummy ที่เรียนจาก TRAIN+VAL
            Dummy เป็นฐานตรวจว่าผลเหนือการตอบคลาสส่วนใหญ่หรือไม่ โดยไม่ได้ใช้ TEST fit
            ไม่ใช้คะแนนตารางนี้เลือกโมเดลใหม่
            '''),code('''
            baseline_rows=[]
            for task,spec in ce.TASKS.items():
                fit_df=pd.concat([ce.load_split(task,'train'),ce.load_split(task,'val')],ignore_index=True)
                test_df=ce.load_split(task,'test')
                dummy=ce.DummyClassifier(strategy='most_frequent').fit(
                    fit_df[bundles[task]['feature_columns']],fit_df[spec['target']],sample_weight=ce.clip_weights(fit_df))
                m=ce.metric_values(test_df,spec['target'],dummy.predict(test_df[bundles[task]['feature_columns']]),spec['labels'])
                baseline_rows.append(dict(task=spec['title'],selected_f1=results[task]['conditional']['clip_balanced_macro_f1'],
                                          dummy_f1=m['clip_balanced_macro_f1']))
            display(pd.DataFrame(baseline_rows).round(4))
            ''')]
    for task,spec in ce.TASKS.items():
        cells += [md(f'''
            ## 5 · รายละเอียดงาน {spec['title']}
            ตารางแรกเป็นจำนวนเฟรมจริง ส่วนตารางที่สองถ่วงน้ำหนักคลิปเท่ากัน
            Confusion matrix มีคอลัมน์ “จุดไม่ครบ” เพื่อเห็นภาพที่ pipeline ประเมินไม่ได้
            แถวเป็นคำตอบจริง คอลัมน์เป็นผลทำนาย
            '''),code(f'''
            task = {task!r}
            metric = results[task]
            display(pd.DataFrame(metric['classification_reports']['unweighted']).T.round(4))
            display(pd.DataFrame(metric['classification_reports']['clip_balanced']).T.round(4))
            fig=ce.plot_confusions(task,rows_by_task[task])
            fig.savefig(REPORT/SPLIT/f'confusion_{{task}}.png'); plt.show()
            ''')]
        cells += [md(f'### 5 · {spec["title"]}: ผลรายคนและรายคลิป'),code(f'''
            task = {task!r}
            expert_table=pd.DataFrame(results[task]['per_expert']).T
            display(expert_table.round(4))
            # A class can be absent for one player even when present in the full split.
            expert_classes=[]
            for expert,g in rows_by_task[task].groupby('expert'):
                observed=[label for label in ce.TASKS[task]['labels'] if (g.truth==label).any()]
                expert_classes.append(dict(expert=expert,
                    true_class_counts=g.truth.value_counts().to_dict(),
                    missing_classes=[label for label in ce.TASKS[task]['labels'] if label not in observed],
                    macro_f1_observed_classes=ce.f1_score(g.truth,g.prediction,labels=observed,
                        average='macro',sample_weight=ce.clip_weights(g),zero_division=0)))
            display(pd.DataFrame(expert_classes).round(4))
            print('The chart uses fixed classes. Missing classes can lower Macro F1 even without errors; read class counts and accuracy together.')
            per_clip=pd.read_csv(REPORT/SPLIT/'selected'/f'{{task}}_per_clip.csv')
            display(per_clip.sort_values('accuracy').head(12).round(4))
            fig,ax=plt.subplots(figsize=(6,3))
            bars=ax.bar(expert_table.index,expert_table.clip_balanced_macro_f1,color=['#21677c','#e59437'])
            ax.bar_label(bars,fmt='%.3f'); ax.set(ylim=(0,1.12),title='{spec['title']} · all reviewed',ylabel='Clip-balanced Macro F1')
            fig.tight_layout(); fig.savefig(REPORT/SPLIT/f'expert_{{task}}.png'); plt.show()
            ''')]
    cells += [md('''
        ## 6.1 · ตรวจสองอาการพร้อมกัน
        Exact match คือทายก้มหน้าและไหล่เอียงถูกทั้งคู่ในเฟรมเดียวกัน
        Joint recall คือภาพที่ผิดทั้งสองอาการแล้วตรวจพบทั้งสอง; หากไม่มีภาพดังกล่าวจะไม่มีค่าคะแนนนี้
        จำนวนคลิปที่มีทั้งสองอาการสำคัญกว่าจำนวนเฟรมเพียงอย่างเดียว
        '''),code('''
        joint=ce.posture_joint(SPLIT,rows_by_task,REPORT)
        display(pd.DataFrame([joint]).round(4))
        ''')]
    cells += [md('''
        ## 6.2 · เปิดตัวอย่างที่ทายผิดหรือประเมินไม่ได้
        ตารางแสดงคำตอบจริง/ผลทำนายและตำแหน่งไฟล์ ยังคงตัวอย่างเหล่านี้ไว้ในคะแนน
        ภาพตัวอย่างเป็นการทบทวนผล ไม่ใช้แก้ค่าหลังเห็น TEST ในรอบนี้
        '''),code('''
        errors=[]
        for task,rows in rows_by_task.items():
            selected=rows.loc[~rows.is_correct,['frame_path','clip_id','expert','timestamp_s','truth','prediction','geometry_status']].copy()
            selected.insert(0,'task',task)
            errors.append(selected)
        error_table=pd.concat(errors,ignore_index=True)
        display(error_table.groupby(['task','truth','prediction']).size().rename('frames').reset_index())
        display(error_table.head(20))
        error_table.to_csv(REPORT/SPLIT/'all_errors.csv',index=False,encoding='utf-8-sig')
        ''')]
    cells += [code('''
        for task in ce.TASKS:
            examples=error_table.loc[error_table.task==task].drop_duplicates('clip_id').head(2)
            for _,row in examples.iterrows():
                display(Markdown(f"**{task}** · {row.expert} · {row.timestamp_s:.2f}s · จริง `{row.truth}` / ทำนาย `{row.prediction}`"))
                image=ce.ROOT/row.frame_path
                if image.exists(): display(Image(filename=str(image),width=440))
        ''')]
    if is_test:
        cells += [md('''
            ## 7.1 · ช่วงความไม่แน่นอนจากจำนวนคลิปน้อย
            Bootstrap สุ่มซ้ำทั้งคลิป 500 ครั้ง ไม่สุ่มเฟรมแยกจากกัน
            ช่วง 95% เป็นการอธิบายความแปรปรวนในชุดนี้เท่านั้น มีเพียงสองคน และบางครั้งสุ่มได้ไม่ครบคลาส
            จึงไม่ใช่การรับประกันผลกับผู้เล่นใหม่
            '''),code('''
            intervals={task:ce.bootstrap_clip_f1(rows,task,repeats=500,seed=42) for task,rows in rows_by_task.items()}
            ce.save_json(REPORT/'test/bootstrap_intervals.json',intervals)
            display(pd.DataFrame([dict(task=ce.TASKS[task]['title'],
                f1=results[task]['all_reviewed']['clip_balanced_macro_f1'],
                low_95=value['low'],high_95=value['high']) for task,value in intervals.items()]).round(4))
            ''')]
        cells += [md('''
            ## 7.2 · อ่านผล VAL และ TEST ให้ถูกต้อง
            VAL ใช้โมเดล fit TRAIN; TEST ใช้โมเดล fit TRAIN+VAL จึงไม่ได้เป็นการประเมิน estimator ตัวเดียวกัน
            ตารางนี้ช่วยดูความต่างของชุดข้อมูล แต่ห้ามตีความว่า TEST สูงกว่าแปลว่าโมเดลดีขึ้นจากการปรับค่า
            '''),code('''
            validation=ce.read_json(REPORT/'val/results.json')
            comparison=pd.DataFrame([dict(task=ce.TASKS[task]['title'],
                val_f1=validation[task]['all_reviewed']['clip_balanced_macro_f1'],
                test_f1=results[task]['all_reviewed']['clip_balanced_macro_f1'],
                val_coverage=validation[task]['all_reviewed']['clip_balanced_coverage'],
                test_coverage=results[task]['all_reviewed']['clip_balanced_coverage']) for task in ce.TASKS])
            display(comparison.round(4))
            fig,ax=plt.subplots(figsize=(10,4)); x=np.arange(len(comparison)); width=.35
            ax.bar(x-width/2,comparison.val_f1,width,label='VAL: fit TRAIN')
            ax.bar(x+width/2,comparison.test_f1,width,label='TEST: fit TRAIN+VAL')
            ax.set_xticks(x,comparison.task); ax.set(ylim=(0,1),ylabel='All reviewed · clip-balanced Macro F1'); ax.legend()
            fig.tight_layout(); fig.savefig(REPORT/'test/val_test_comparison.png'); plt.show()
            ''')]
    cells += [md('''
        ## 8.1 · สรุปผลและข้อจำกัด
        อ่านทั้ง F1/Recall รายคลาส ผลรายคน Coverage และตัวอย่างผิดควบคู่กัน
        การตรวจคันชักเป็นการทดลองจากร่างกาย; ยังไม่มีข้อมูลผู้เล่นคนที่สามหรือกล้อง/สถานที่ใหม่ที่กันไว้ทั้งคน
        ไม่มีการนำรุ่นนี้ไปใช้เว็บอัตโนมัติ และคะแนนนี้ยังไม่รวม temporal smoothing/uncertainty guard ของเว็บ
        '''),code('''
        lines=[]
        for task,r in results.items():
            m=r['all_reviewed']; u=r['conditional']
            lines.append(f"- **{ce.TASKS[task]['title']}**: {r['family']}, F1 แบบคลิปเท่ากันเมื่อจุดครบ **{u['clip_balanced_macro_f1']:.3f}**, รวมจุดไม่ครบ **{m['clip_balanced_macro_f1']:.3f}**, coverage **{m['clip_balanced_coverage']:.1%}**, {m['frames']} เฟรม / {m['clips']} คลิป")
        display(Markdown('\\n'.join(lines)))
        assert WEB_BEFORE == ce.web_fingerprints(), 'Web model changed during this run'
        print('Web model unchanged: verified')
        print('Report directory:',REPORT/SPLIT)
        ''')]
    return notebook(cells)


def execute(nb, path):
    import asyncio
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    nbf.write(nb,path)
    print(f'Executing {path.name}',flush=True)
    def report_cell(cell, cell_index, **kwargs):
        if cell.cell_type == 'code':
            print(f'  Cell {cell_index+1}: {cell.source.splitlines()[0][:90]}',flush=True)
    client=NotebookClient(nb,timeout=1800,kernel_name='sawuai',on_cell_start=report_cell,
                          resources={'metadata':{'path':str(ce.ROOT.parent)}})
    try:
        client.execute()
    finally:
        nbf.write(nb,path)
    errors=[o for c in nb.cells if c.cell_type=='code' for o in c.get('outputs',[]) if o.output_type=='error']
    if errors:
        raise RuntimeError(errors[0]['evalue'])
    print(f'Completed {path.name}: {sum(c.cell_type=="code" for c in nb.cells)} code cells',flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',help='Resume or rebuild an existing independent training run')
    args=parser.parse_args()
    summary,manifests=ce.verify_prepared_data()
    if args.run:
        run=args.run
    else:
        run,_,_,_=ce.new_run(42,3,TREE_GRID,FOREST_GRID,ce.web_fingerprints(),summary,manifests)
    NB_DIR.mkdir(parents=True,exist_ok=True)
    ce.save_json(NB_DIR/'run.json',dict(run=run))
    # Create all three files up front, then execute strictly TRAIN -> VAL -> TEST.
    books=[('01_train_combined_experts.ipynb',training_book(run)),
           ('02_validation_results.ipynb',evaluation_book(run,'val')),
           ('03_test_results.ipynb',evaluation_book(run,'test'))]
    for name,nb in books: nbf.write(nb,NB_DIR/name)
    for name,nb in books: execute(nb,NB_DIR/name)
    from .summarize_combined_training import summarize
    summarize(run)
    print('All three notebooks completed:',run,flush=True)


if __name__=='__main__':
    main()
