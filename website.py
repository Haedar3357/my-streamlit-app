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
  
    reshaped_title = arabic_reshaper.reshape(data["title"])
    bidi_title = get_display(reshaped_title)
    c.drawRightString(500, 750, bidi_title)  # رسم العنوان الرئيسي من اليمين لليسار

    # إضافة بيانات الموظف إلى ملف PDF
    y_position = 730
    del data["title"]
    for label, value in data.items():
        # إعادة تشكيل العنوان والقيمة
        reshaped_label = arabic_reshaper.reshape(str(label))  
        reshaped_value = arabic_reshaper.reshape(str(value))
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
passwords = ["0102", "1002", "0120", "1314", "2324"]

# إعداد التواريخ
min_date = datetime.date(1900, 1, 1)
max_date = datetime.date.today()

# دالة للتحقق من الحقول المطلوبة
def validate_required_fields(fields):
    missing_fields = []
    for field_name, field_value in fields.items():
        if field_value is None or (isinstance(field_value, str) and field_value.strip() == "":
            missing_fields.append(field_name)
        elif isinstance(field_value, list) and len(field_value) == 0:
            missing_fields.append(field_name)
    return missing_fields

# دالة لإضافة خلفية
def add_background(image_path):
    with open(image_path, "rb") as img_file:
        encoded_string = base64.b64encode(img_file.read()).decode()
    
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpg;base64,{encoded_string}");
            background-size: cover;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

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
        <div style="flex-direction: row-reverse; text-align: left;">
            <img src="data:image/png;base64,{logo_encoded}" style="margin-right: 10px;">
            <span style="font-size: 24px; font-weight: bold;">
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
    user_password = st.text_input("أدخل كلمة السر *", type="password")

    if user_password in passwords:
        with st.form("employee_form"):
            st.markdown("**جميع الحقول مطلوبة**")
            
            computer_no = st.text_input("رقم الحاسبة *")
            badge_no = st.text_input("رقم الشعار *")
            department = st.text_input("القسم *")
            full_name = st.text_input("الإسم الرباعي واللقب *")
            mother_name = st.text_input("اسم الأم الثلاثي *")
            birth_date = st.date_input("المواليد *", min_value=min_date, max_value=max_date)
            marital_status = st.selectbox("متزوج *", ["نعم", "لا"])
            
            if marital_status == "نعم":
                marriage_contract = st.file_uploader("ارفاق عقد الزواج *", type=["jpg", "jpeg", "png", "pdf"])
            else:
                marriage_contract = None
                
            family_count = st.number_input("عدد الأفراد *", min_value=0, step=1)
            address = st.text_input("عنوان السكن *")
            nearby_landmark = st.text_input("أقرب نقطه دالة *")
            appointment_date = st.date_input("تاريخ التعيين *", min_value=min_date, max_value=max_date)
            administrative_order = st.file_uploader("الامر الاداري للتعيين *", type=["jpg", "jpeg", "png", "pdf"])
            permit_number = st.text_input("رقم التصريح *")
            permit_copy = st.file_uploader("ارفاق نسخة من التصريح *", type=["jpg", "jpeg", "png", "pdf"])
            national_id_front = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الواجهه *", type=["jpg", "jpeg", "png", "pdf"])
            national_id_back = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الضهر *", type=["jpg", "jpeg", "png", "pdf"])
            housing_card_front = st.file_uploader("ارفاق نسخة من بطاقه السكن/ الوجه *", type=["jpg", "jpeg", "png", "pdf"])
            housing_card_back = st.file_uploader("ارفاق نسخة من بطاقه السكن/الضهر *", type=["jpg", "jpeg", "png", "pdf"])
            mobile = st.text_input("رقم الموبايل *")
            data_entry_name = st.text_input("اسم مدخل البيانات *")

            submitted = st.form_submit_button("حفظ البيانات")
            
            if submitted:
                required_fields = {
                    "رقم الحاسبة": computer_no,
                    "رقم الشعار": badge_no,
                    "القسم": department,
                    "الإسم الرباعي واللقب": full_name,
                    "اسم الأم الثلاثي": mother_name,
                    "عنوان السكن": address,
                    "أقرب نقطه دالة": nearby_landmark,
                    "رقم التصريح": permit_number,
                    "رقم الموبايل": mobile,
                    "اسم مدخل البيانات": data_entry_name,
                    "الامر الاداري للتعيين": administrative_order,
                    "نسخة من التصريح": permit_copy,
                    "البطاقة الوطنية/الواجهه": national_id_front,
                    "البطاقة الوطنية/الضهر": national_id_back,
                    "بطاقة السكن/الوجه": housing_card_front,
                    "بطاقة السكن/الضهر": housing_card_back
                }
                
                if marital_status == "نعم":
                    required_fields["عقد الزواج"] = marriage_contract
                
                missing_fields = validate_required_fields(required_fields)
                
                if missing_fields:
                    st.error(f"الحقول التالية مطلوبة: {', '.join(missing_fields)}")
                else:
                    try:
                        # هنا يتم حفظ البيانات بعد التحقق
                        st.success("تم التحقق من جميع البيانات بنجاح! يمكن الآن حفظ البيانات.")
                        # إضافة كود الحفظ الفعلي هنا
                    except Exception as e:
                        st.error(f"حدث خطأ أثناء الحفظ: {str(e)}")

    else:
        if user_password:
            st.error("كلمة السر غير صحيحة. يرجى المحاولة مرة أخرى.")

# صفحة إضافة عقد
elif page == "إضافة بيانات العقود":
    st.title("إضافة بيانات العقد")
    user_password = st.text_input("أدخل كلمة السر *", type="password")

    if user_password in passwords:
        with st.form("contract_form"):
            st.markdown("**جميع الحقول مطلوبة**")
            
            computer_no = st.text_input("رقم الحاسبة *")
            badge_no = st.text_input("رقم الشعار *")
            department = st.text_input("القسم *")
            full_name = st.text_input("الإسم الرباعي واللقب *")
            mother_name = st.text_input("اسم الأم الثلاثي *")
            birth_date = st.date_input("المواليد *", min_value=min_date, max_value=max_date)
            marital_status = st.selectbox("متزوج *", ["نعم", "لا"])
            
            if marital_status == "نعم":
                marriage_contract = st.file_uploader("ارفاق عقد الزواج *", type=["jpg", "jpeg", "png", "pdf"])
            else:
                marriage_contract = None
                
            family_count = st.number_input("عدد الأفراد *", min_value=0, step=1)
            address = st.text_input("عنوان السكن *")
            nearby_landmark = st.text_input("أقرب نقطه دالة *")
            contract_date = st.date_input("تاريخ التعاقد *", min_value=min_date, max_value=max_date)
            administrative_order = st.file_uploader("الامر الاداري للتعاقد *", type=["jpg", "jpeg", "png", "pdf"])
            permit_number = st.text_input("رقم التصريح *")
            permit_copy = st.file_uploader("ارفاق نسخة من التصريح *", type=["jpg", "jpeg", "png", "pdf"])
            national_id_front = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الواجهه *", type=["jpg", "jpeg", "png", "pdf"])
            national_id_back = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الضهر *", type=["jpg", "jpeg", "png", "pdf"])
            housing_card_front = st.file_uploader("ارفاق نسخة من بطاقه السكن/ الوجه *", type=["jpg", "jpeg", "png", "pdf"])
            housing_card_back = st.file_uploader("ارفاق نسخة من بطاقه السكن/الضهر *", type=["jpg", "jpeg", "png", "pdf"])
            mobile = st.text_input("رقم الموبايل *")
            data_entry_name = st.text_input("اسم مدخل البيانات *")

            submitted = st.form_submit_button("حفظ البيانات")
            
            if submitted:
                required_fields = {
                    "رقم الحاسبة": computer_no,
                    "رقم الشعار": badge_no,
                    "القسم": department,
                    "الإسم الرباعي واللقب": full_name,
                    "اسم الأم الثلاثي": mother_name,
                    "عنوان السكن": address,
                    "أقرب نقطه دالة": nearby_landmark,
                    "رقم التصريح": permit_number,
                    "رقم الموبايل": mobile,
                    "اسم مدخل البيانات": data_entry_name,
                    "الامر الاداري للتعاقد": administrative_order,
                    "نسخة من التصريح": permit_copy,
                    "البطاقة الوطنية/الواجهه": national_id_front,
                    "البطاقة الوطنية/الضهر": national_id_back,
                    "بطاقة السكن/الوجه": housing_card_front,
                    "بطاقة السكن/الضهر": housing_card_back
                }
                
                if marital_status == "نعم":
                    required_fields["عقد الزواج"] = marriage_contract
                
                missing_fields = validate_required_fields(required_fields)
                
                if missing_fields:
                    st.error(f"الحقول التالية مطلوبة: {', '.join(missing_fields)}")
                else:
                    try:
                        st.success("تم التحقق من جميع البيانات بنجاح! يمكن الآن حفظ البيانات.")
                    except Exception as e:
                        st.error(f"حدث خطأ أثناء الحفظ: {str(e)}")

    else:
        if user_password:
            st.error("كلمة السر غير صحيحة. يرجى المحاولة مرة أخرى.")

# صفحة إضافة عاملين بصفة شراء خدمات
elif page == "إضافة بيانات العاملين بصفة شراء خدمات":
    st.title("إضافة بيانات العاملين بصفة شراء خدمات")
    user_password = st.text_input("أدخل كلمة السر *", type="password")

    if user_password in passwords:
        with st.form("service_form"):
            st.markdown("**جميع الحقول مطلوبة**")
            
            computer_no = st.text_input("رقم الحاسبة *")
            department = st.text_input("القسم *")
            full_name = st.text_input("الإسم الرباعي واللقب *")
            mother_name = st.text_input("اسم الأم الثلاثي *")
            birth_date = st.date_input("المواليد *", min_value=min_date, max_value=max_date)
            address = st.text_input("عنوان السكن *")
            nearby_landmark = st.text_input("أقرب نقطه دالة *")
            referral_date = st.date_input("تاريخ الإحالة *", min_value=min_date, max_value=max_date)
            referral_duration = st.number_input("مدة الإحالة *", min_value=1, step=1)
            referral_copy = st.file_uploader("ارفاق نسخة من الإحالة *", type=["jpg", "jpeg", "png", "pdf"])
            permit_number = st.text_input("رقم التصريح *")
            permit_copy = st.file_uploader("ارفاق نسخة من التصريح *", type=["jpg", "jpeg", "png", "pdf"])
            national_id_front = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الواجهه *", type=["jpg", "jpeg", "png", "pdf"])
            national_id_back = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الضهر *", type=["jpg", "jpeg", "png", "pdf"])
            housing_card_front = st.file_uploader("ارفاق نسخة من بطاقه السكن/ الوجه *", type=["jpg", "jpeg", "png", "pdf"])
            housing_card_back = st.file_uploader("ارفاق نسخة من بطاقه السكن/الضهر *", type=["jpg", "jpeg", "png", "pdf"])
            mobile = st.text_input("رقم الموبايل *")
            data_entry_name = st.text_input("اسم مدخل البيانات *")

            submitted = st.form_submit_button("حفظ البيانات")
            
            if submitted:
                required_fields = {
                    "رقم الحاسبة": computer_no,
                    "القسم": department,
                    "الإسم الرباعي واللقب": full_name,
                    "اسم الأم الثلاثي": mother_name,
                    "عنوان السكن": address,
                    "أقرب نقطه دالة": nearby_landmark,
                    "رقم التصريح": permit_number,
                    "رقم الموبايل": mobile,
                    "اسم مدخل البيانات": data_entry_name,
                    "نسخة من الإحالة": referral_copy,
                    "نسخة من التصريح": permit_copy,
                    "البطاقة الوطنية/الواجهه": national_id_front,
                    "البطاقة الوطنية/الضهر": national_id_back,
                    "بطاقة السكن/الوجه": housing_card_front,
                    "بطاقة السكن/الضهر": housing_card_back
                }
                
                missing_fields = validate_required_fields(required_fields)
                
                if missing_fields:
                    st.error(f"الحقول التالية مطلوبة: {', '.join(missing_fields)}")
                else:
                    try:
                        st.success("تم التحقق من جميع البيانات بنجاح! يمكن الآن حفظ البيانات.")
                    except Exception as e:
                        st.error(f"حدث خطأ أثناء الحفظ: {str(e)}")

    else:
        if user_password:
            st.error("كلمة السر غير صحيحة. يرجى المحاولة مرة أخرى.")


