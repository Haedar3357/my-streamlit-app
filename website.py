import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import tempfile
import base64
import datetime
import os
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import arabic_reshaper
from bidi.algorithm import get_display


def generate_pdf(data, images):
    # إنشاء ملف PDF جديد
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(temp_file.name, pagesize=letter)

    # إضافة الخط العربي
    font_path = "DejaVuSans.ttf"  # تأكد من أن الخط يدعم العربية
    pdfmetrics.registerFont(TTFont('DejaVu', font_path))
    c.setFont("DejaVu", 12)

    # إعداد العنوان الرئيسي للنموذج (من اليمين لليسار باستخدام arabic_reshaper و python-bidi)
    title = "نموذج بيانات الموظف"
    reshaped_title = arabic_reshaper.reshape(title)
    bidi_title = get_display(reshaped_title)
    c.drawRightString(500, 750, bidi_title)  # رسم العنوان الرئيسي من اليمين لليسار

    # إضافة بيانات الموظف إلى ملف PDF
    y_position = 730
    for label, value in data.items():
        # إعادة تشكيل العنوان والقيمة
        reshaped_label = arabic_reshaper.reshape(label)
        reshaped_value = arabic_reshaper.reshape(value)
        bidi_label = get_display(reshaped_label)
        bidi_value = get_display(reshaped_value)
        
        # تنسيق السطر ليكون "القيمة: العنوان"
        line_text = f"{bidi_value} : {bidi_label}"
        
        # كتابة السطر بالكامل من اليمين لليسار باستخدام drawRightString
        c.drawRightString(500, y_position, line_text)
        y_position -= 20  # تقليل الموضع العمودي للكتابة أسفل السطر السابق

    # إضافة عنوان المرفقات بشكل صحيح
    reshaped_label = arabic_reshaper.reshape("المرفقات:")
    bidi_label = get_display(reshaped_label)
    c.drawRightString(500, y_position, bidi_label)
    y_position -= 30

    # إضافة الصور مع وضعها بشكل محاذي للعنوان الخاص بها وزيادة الحجم مع استخدام صفحات جديدة
    for label, img in images.items():
        if img:
            # حفظ الصورة مؤقتًا
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_img:
                img_path = temp_img.name
                with open(img_path, 'wb') as f:
                    f.write(img.getvalue())  # الكتابة إلى الملف المؤقت

                # تحضير النص الخاص بالعنوان واستخدام الاتجاه من اليمين لليسار
                reshaped_label = arabic_reshaper.reshape(label)
                bidi_label = get_display(reshaped_label)
                
                # رسم العنوان في موضع محدد
                c.drawRightString(500, y_position, bidi_label)
                y_position -= 20  # خفض الموضع قليلاً بعد العنوان
                
                # رسم الصورة بحجم أكبر في الصفحة الحالية
                c.drawImage(img_path, 200, y_position-300, width=300, height=300)  # تكبير الصورة
                y_position -= 320  # خفض الموضع بشكل أكبر بعد إضافة الصورة

                # إضافة صفحة جديدة إذا كانت هناك صورة أخرى
                c.showPage()

                # إعادة تعيين إعدادات الخط والنص في الصفحة الجديدة
                pdfmetrics.registerFont(TTFont('DejaVu', font_path))
                c.setFont("DejaVu", 12)
                y_position = 750  # إعادة تعيين الموضع في الصفحة الجديدة
                
    # حفظ الملف
    c.save()
    return temp_file.name


# تحديد تاريخ أدنى وحد أقصى
min_date = datetime.date(1900, 1, 1)
max_date = datetime.date.today()

scope = ["https://spreadsheets.google.com/feeds", 
         "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file", 
         "https://www.googleapis.com/auth/drive"]

# قراءة بيانات الاعتماد من st.secrets
try:
    credentials_dict = st.secrets["gcp_service_account"]  # جلب بيانات الاعتماد مباشرة من Streamlit secrets
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    gc = gspread.authorize(credentials)
    
    # فتح ملفات Google Sheet لكل قسم
    sh_employees = gc.open("بيانات الموظفين")
    sh_contracts = gc.open("بيانات العقود")
    sh_service = gc.open("بيانات الخدمة")

except Exception as e:
    st.error(f"حدث خطأ في إعداد الاتصال: {e}")
# إعداد Google Drive
gauth = GoogleAuth()
gauth.credentials = credentials
drive = GoogleDrive(gauth)


# دالة لرفع الملفات إلى Google Drive وإرجاع الروابط
def upload_files(files):
    links = []
    for file in files:
        if file:
            try:
                file_drive = drive.CreateFile({'title': file.name})
                
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(file.getvalue())
                    temp_file.close()

                file_drive.SetContentFile(temp_file.name)
                file_drive.Upload()

                file_drive.InsertPermission({
                    'type': 'anyone',
                    'role': 'reader'
                })

                link = file_drive['alternateLink']
                links.append(link)
            except Exception as e:
                st.error(f"فشل رفع الملف: {file.name} - {e}")
                links.append(None)
        else:
            links.append(None)
    return links
def load_css():
    css_code = """
    /* تكبير حجم الخط وتغيير اتجاه النصوص للموقع بالكامل إلى اليمين */
    body {
        font-family: Arial, sans-serif;
        direction: rtl;
        text-align: right;
    }
    /* تكبير حجم العناوين */
    .main-title, h1, h2, h3, h4, h5, h6 {
        font-size: 24px; /* حجم أكبر للعناوين */
        font-weight: bold;
        color: #333;
    }
    /* تكبير حجم النصوص فوق حقول الإدخال */
    label {
        font-size: 20px; /* تكبير حجم النص */
        font-weight: bold;
        color: #333;
    }
    /* محاذاة الشعار بجانب العنوان */
    .header-container {
        display: flex;
        align-items: left;
        justify-content: flex-end;
        margin-top: 20px;
    }
    .logo {
        width: 115px;
        height: auto;
        margin-left: 15px; /* فراغ بين الشعار والعنوان */
    }
    .footer {
        position: fixed;
        bottom: 20px;
        width: 100%;
        text-align: center;
        font-size: 14px;
        color: #333;
    }
    """
    st.markdown(f"<style>{css_code}</style>", unsafe_allow_html=True)

# دالة لتحميل خلفية الصورة للصفحة الرئيسية كخلفية شاملة شفافة
def add_background(image_file):
    with open(image_file, "rb") as img:
        encoded = base64.b64encode(img.read()).decode()
    st.markdown(
        f"""
        <style>
          .background {{
             position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background-image: url("data:image/png;base64,{encoded}");
            background-size: 80% 100%; /* يضمن تغطية الشاشة بالكامل */
            background-position: left center;
            background-repeat: no-repeat;
            opacity: 0.3; /* ضبط الشفافية حسب الحاجة */
        }}
            
           

        .main-title {{
            font-size: 35px;
            font-weight: bold;
            text-align: right;
            color: #333;
            margin-top: 20px;
            z-index: 1;
            position: relative;
        }}
        </style>
        
        <div class="background"></div>
        """,
        unsafe_allow_html=True,
    )

# تحميل CSS
load_css()


# قائمة كلمات السر المقبولة
passwords = ["77665", "66554", "55664", "33556", "22110"]


# الصفحة الرئيسية
st.sidebar.title("التنقل بين الصفحات")
page = st.sidebar.selectbox("اختر الصفحة", ["الصفحة الرئيسية", "إضافة بيانات الموظفين", "إضافة بيانات العقود", "إضافة بيانات العاملين بصفة شراء خدمات"])


if page == "الصفحة الرئيسية":
    add_background("background.jpg")

    # الشعار والعنوان
    logo_path = "logo.jpg"
    with open(logo_path, "rb") as img_file:
        logo_encoded = base64.b64encode(img_file.read()).decode()
    st.markdown(
        f"""
        <div class="header-container" style="flex-direction: row-reverse; text-align: left;">
            <img src="data:image/png;base64,{logo_encoded}" class="logo" style="margin-right: 10px;">
            <span class="main-title">
                إضافة بيانات العاملين في شركة مصافي الشمال
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# صفحة إضافة موظف
elif page == "إضافة بيانات الموظفين":
    st.title("إضافة بيانات الموظف")

    # إدخال كلمة السر
    user_password = st.text_input("أدخل كلمة السر", type="password")

    if user_password in passwords:  # التحقق من وجود كلمة السر في القائمة
        computer_no = st.text_input("رقم الحاسبة")
        badge_no = st.text_input("رقم الشعار")
        department = st.text_input("القسم")
        full_name = st.text_input("الإسم الرباعي واللقب")
        mother_name = st.text_input("اسم الأم الثلاثي")
        birth_date = st.date_input("المواليد", min_value=min_date, max_value=max_date)
        marital_status = st.selectbox("متزوج", ["نعم", "لا"])
        marriage_contract = st.file_uploader("ارفاق عقد الزواج", type=["jpg", "jpeg", "png", "pdf"]) if marital_status == "نعم" else None
        family_count = st.number_input("عدد الأفراد", min_value=0, step=1)
        first_child = st.text_input("اول طفل")
        second_child = st.text_input("ثاني طفل")
        third_child = st.text_input("ثالث طفل")
        fourth_child = st.text_input("رابع طفل")
        address = st.text_input("عنوان السكن")
        nearby_landmark = st.text_input("أقرب نقطه دالة")
        appointment_date = st.date_input("تاريخ التعيين", min_value=min_date, max_value=max_date)
        administrative_order = st.file_uploader("الامر الاداري للتعيين", type=["jpg", "jpeg", "png", "pdf"])
        permit_number = st.text_input("رقم التصريح")
        permit_copy = st.file_uploader("ارفاق نسخة من التصريح", type=["jpg", "jpeg", "png", "pdf"])
        national_id_front = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الواجهه", type=["jpg", "jpeg", "png", "pdf"])
        national_id_back = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الضهر", type=["jpg", "jpeg", "png", "pdf"])
        housing_card_front = st.file_uploader("ارفاق نسخة من بطاقه السكن/ الوجه", type=["jpg", "jpeg", "png", "pdf"])
        housing_card_back = st.file_uploader("ارفاق نسخة من بطاقه السكن/الضهر", type=["jpg", "jpeg", "png", "pdf"])
        mobile = st.text_input("رقم الموبايل")
        data_entry_name = st.text_input("اسم مدخل البيانات")

        if st.button("حفظ البيانات"):
            file_links = upload_files([marriage_contract if marital_status == "نعم" else None, administrative_order, permit_copy, national_id_front, national_id_back, housing_card_front, housing_card_back])
            worksheet = sh_employees.sheet1
            worksheet.append_row([computer_no, badge_no, department, full_name, mother_name, str(birth_date), marital_status, file_links[0] if marital_status == "نعم" else None, family_count, first_child, second_child, third_child, fourth_child, address, nearby_landmark, str(appointment_date), file_links[1], permit_number, file_links[2], file_links[3], file_links[4], file_links[5], file_links[6], mobile, data_entry_name])
            st.success("تم حفظ البيانات بنجاح!")
        if st.button("تحميل كملف PDF"):
            # البيانات المراد إضافتها في ملف PDF
            data = {
                "رقم الحاسبة": computer_no,
                "رقم الشعار": badge_no,
                "القسم": department,
                "الإسم الرباعي واللقب": full_name,
                "اسم الأم الثلاثي": mother_name,
                "المواليد": str(birth_date),
                "الحالة الزوجية": marital_status,
                "عدد الأفراد": family_count,
                "اول طفل": first_child,
                "ثاني طفل": second_child,
                "ثالث طفل": third_child,
                "رابع طفل": fourth_child,
                "عنوان السكن": address,
                "أقرب نقطه دالة": nearby_landmark,
                "تاريخ التعيين": str(appointment_date),
                "رقم التصريح": permit_number,
                "رقم الموبايل": mobile,
                "اسم مدخل البيانات": data_entry_name
            }

            # إعداد الملفات
            images = {
                "عقد الزواج": marriage_contract if marital_status == "نعم" else None,
                "الامر الاداري للتعيين": administrative_order,
                "نسخة من التصريح": permit_copy,
                "البطاقة الوطنية/الواجهه": national_id_front,
                "البطاقة الوطنية/الضهر": national_id_back,
                "بطاقة السكن/الوجه": housing_card_front,
                "بطاقة السكن/الضهر": housing_card_back
            }

            # إنشاء ملف PDF
            pdf_file_path = generate_pdf(data, images)
            with open(pdf_file_path, "rb") as pdf_file:
                st.download_button(
                    label="اضغط هنا للتحميل",
                    data=pdf_file,
                    file_name="بيانات_الموظف.pdf",
                    mime="application/pdf"
                )
    else:
        if user_password:  # فقط إظهار الرسالة إذا كانت هناك محاولة إدخال كلمة سر
            st.error("كلمة السر غير صحيحة. يرجى المحاولة مرة أخرى.")

# --- الصفحة الثانية: إضافة عقد ---
elif page == "إضافة بيانات العقود":
    st.title("إضافة بيانات العقد")
    user_password = st.text_input("أدخل كلمة السر", type="password")

    if user_password in passwords:  # التحقق من وجود كلمة السر في القائمة
        # إدخال الحقول النصية
        computer_no = st.text_input("رقم الحاسبة")
        badge_no = st.text_input("رقم الشعار")
        department = st.text_input("القسم")
        full_name = st.text_input("الإسم الرباعي واللقب")
        mother_name = st.text_input("اسم الأم الثلاثي")
        birth_date = st.date_input("المواليد", min_value=min_date, max_value=max_date)
        marital_status = st.selectbox("متزوج", ["نعم", "لا"])
        marriage_contract = st.file_uploader("ارفاق عقد الزواج", type=["jpg", "jpeg", "png", "pdf"]) if marital_status == "نعم" else None
        family_count = st.number_input("عدد الأفراد", min_value=0, step=1)
        
        # إدخال أسماء الأطفال
        first_child = st.text_input("اول طفل")
        second_child = st.text_input("ثاني طفل")
        third_child = st.text_input("ثالث طفل")
        fourth_child = st.text_input("رابع طفل")
        
        # إدخال البيانات المتبقية
        address = st.text_input("عنوان السكن")
        nearby_landmark = st.text_input("أقرب نقطه دالة")
        contract_date = st.date_input("تاريخ التعاقد", min_value=min_date, max_value=max_date)
        administrative_order = st.file_uploader("الامر الاداري للتعاقد", type=["jpg", "jpeg", "png", "pdf"])
        permit_number = st.text_input("رقم التصريح")
        permit_copy = st.file_uploader("ارفاق نسخة من التصريح", type=["jpg", "jpeg", "png", "pdf"])
        
        # إدخال نسخ الوثائق
        national_id_front = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الواجهه", type=["jpg", "jpeg", "png", "pdf"])
        national_id_back = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الضهر", type=["jpg", "jpeg", "png", "pdf"])
        housing_card_front = st.file_uploader("ارفاق نسخة من بطاقه السكن/ الوجه", type=["jpg", "jpeg", "png", "pdf"])
        housing_card_back = st.file_uploader("ارفاق نسخة من بطاقه السكن/الضهر", type=["jpg", "jpeg", "png", "pdf"])
        
        # بيانات إضافية
        mobile = st.text_input("رقم الموبايل")
        data_entry_name = st.text_input("اسم مدخل البيانات")
        
        # زر لحفظ البيانات 
        if st.button("حفظ البيانات"):
            # رفع الملفات
            file_links = upload_files([
                marriage_contract if marital_status == "نعم" else None,
                administrative_order,
                permit_copy,
                national_id_front,
                national_id_back,
                housing_card_front,
                housing_card_back
            ])
            
            # كتابة البيانات إلى Google Sheets للعقود
            worksheet = sh_contracts.sheet1
            worksheet.append_row([computer_no, badge_no, department, full_name, mother_name, str(birth_date),
                                marital_status, file_links[0] if marital_status == "نعم" else None, family_count,
                                first_child, second_child, third_child, fourth_child, address, nearby_landmark,
                                str(contract_date), file_links[1], permit_number, file_links[2],
                                file_links[3], file_links[4], file_links[5], file_links[6],
                                mobile, data_entry_name])
            st.success("تم حفظ البيانات بنجاح!")
        # زر لحفظ البيانات وتحميلها كملف PDF
        if st.button("تحميل كملف PDF"):
            # البيانات المراد إضافتها في ملف PDF
            data = {
                "رقم الحاسبة": computer_no,
                "رقم الشعار": badge_no,
                "القسم": department,
                "الإسم الرباعي واللقب": full_name,
                "اسم الأم الثلاثي": mother_name,
                "المواليد": str(birth_date),
                "الحالة الزوجية": marital_status,
                "عدد الأفراد": family_count,
                "اول طفل": first_child,
                "ثاني طفل": second_child,
                "ثالث طفل": third_child,
                "رابع طفل": fourth_child,
                "عنوان السكن": address,
                "أقرب نقطه دالة": nearby_landmark,
                "رقم التصريح": permit_number,
                "رقم الموبايل": mobile,
                "اسم مدخل البيانات": data_entry_name
            }

            # إعداد الملفات (المرفقات) للـ PDF
            images = {
                "عقد الزواج": marriage_contract if marital_status == "نعم" else None,
                "الامر الاداري للتعاقد": administrative_order,
                "نسخة من التصريح": permit_copy,
                "البطاقة الوطنية/الواجهه": national_id_front,
                "البطاقة الوطنية/الضهر": national_id_back,
                "بطاقة السكن/الوجه": housing_card_front,
                "بطاقة السكن/الضهر": housing_card_back
            }

            # إنشاء ملف PDF باستخدام التابع generate_pdf
            pdf_file_path = generate_pdf(data, images)

            # إتاحة زر التحميل للمستخدم
            with open(pdf_file_path, "rb") as pdf_file:
                st.download_button(
                    label="اضغط هنا للتحميل",
                    data=pdf_file,
                    file_name="بيانات_العقد.pdf",
                    mime="application/pdf"
                )
    else:
        if user_password:  # فقط إظهار الرسالة إذا كانت هناك محاولة إدخال كلمة سر
            st.error("كلمة السر غير صحيحة. يرجى المحاولة مرة أخرى.")
elif page == "إضافة بيانات العاملين بصفة شراء خدمات":
    st.title("إضافة بيانات العاملين بصفة شراء خدمات")
    user_password = st.text_input("أدخل كلمة السر", type="password")

    if user_password in passwords:  # التحقق من وجود كلمة السر في القائمة
        # الحقول المطلوبة
        computer_no = st.text_input("رقم الحاسبة")
        department = st.text_input("القسم")
        full_name = st.text_input("الإسم الرباعي واللقب")
        mother_name = st.text_input("اسم الأم الثلاثي")
        birth_date = st.date_input("المواليد", min_value=datetime.date(1900, 1, 1), max_value=datetime.date.today())
        address = st.text_input("عنوان السكن")
        nearby_landmark = st.text_input("أقرب نقطه دالة")
        referral_date = st.date_input("تاريخ الإحالة")
        referral_duration = st.number_input("مدة الإحالة", min_value=1, step=1)
        referral_copy = st.file_uploader("ارفاق نسخة من الإحالة", type=["jpg", "jpeg", "png", "pdf"])
        permit_number = st.text_input("رقم التصريح")
        permit_copy = st.file_uploader("ارفاق نسخة من التصريح", type=["jpg", "jpeg", "png", "pdf"])
        national_id_front = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الواجهه", type=["jpg", "jpeg", "png", "pdf"])
        national_id_back = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الضهر", type=["jpg", "jpeg", "png", "pdf"])
        housing_card_front = st.file_uploader("ارفاق نسخة من بطاقه السكن/ الوجه", type=["jpg", "jpeg", "png", "pdf"])
        housing_card_back = st.file_uploader("ارفاق نسخة من بطاقه السكن/الضهر", type=["jpg", "jpeg", "png", "pdf"])
        mobile = st.text_input("رقم الموبايل")
        data_entry_name = st.text_input("اسم مدخل البيانات")
        
        # زر الحفظ
        if st.button("حفظ البيانات"):
            # رفع الملفات إلى Google Drive والحصول على الروابط
            file_links = upload_files([
                referral_copy, permit_copy, national_id_front, national_id_back, 
                housing_card_front, housing_card_back
            ])
            
            # إضافة البيانات إلى Google Sheets
            worksheet = sh_service.sheet1
            worksheet.append_row([
                computer_no, department, full_name, mother_name, str(birth_date), 
                address, nearby_landmark, str(referral_date), str(referral_duration), 
                file_links[0], permit_number, file_links[1], file_links[2], 
                file_links[3], file_links[4], file_links[5], mobile, data_entry_name
            ])
            
            st.success("تم حفظ البيانات بنجاح!")
         # زر لتحميل البيانات كملف PDF
        if st.button("تحميل كملف PDF"):
            # جمع البيانات المدخلة في معجم (dictionary)
            data = {
                "رقم الحاسبة": computer_no,
                "القسم": department,
                "الإسم الرباعي واللقب": full_name,
                "اسم الأم الثلاثي": mother_name,
                "المواليد": str(birth_date),
                "عنوان السكن": address,
                "أقرب نقطه دالة": nearby_landmark,
                "تاريخ الإحالة": str(referral_date),
                "مدة الإحالة": referral_duration,
                "رقم التصريح": permit_number,
                "رقم الموبايل": mobile,
                "اسم مدخل البيانات": data_entry_name
            }

            # الملفات المرفقة
            images = {
                "نسخة من الإحالة": referral_copy,
                "نسخة من التصريح": permit_copy,
                "البطاقة الوطنية/الواجهه": national_id_front,
                "البطاقة الوطنية/الضهر": national_id_back,
                "بطاقه السكن/ الوجه": housing_card_front,
                "بطاقه السكن/الضهر": housing_card_back
            }

            # إنشاء ملف PDF باستخدام التابع generate_pdf
            pdf_file_path = generate_pdf(data, images)

            # عرض زر لتحميل ملف PDF
            with open(pdf_file_path, "rb") as pdf_file:
                st.download_button(
                    label="اضغط هنا للتحميل كملف PDF",
                    data=pdf_file,
                    file_name="بيانات_العامل_شراء_خدمات.pdf",
                    mime="application/pdf"
                )
        
    else:
        if user_password:  # فقط إظهار الرسالة إذا كانت هناك محاولة إدخال كلمة سر
            st.error("كلمة السر غير صحيحة. يرجى المحاولة مرة أخرى.")

st.markdown("<div class='footer'>تم أعداد وتصميم الاستمارة<br>Ali.H.gma</div>", unsafe_allow_html=True)

