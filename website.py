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
        font-size: 24px;
        font-weight: bold;
        color: #333;
    }
    /* تكبير حجم النصوص فوق حقول الإدخال */
    label {
        font-size: 20px;
        font-weight: bold;
        color: #333;
    }
    /* محاذاة الشعار بجانب العنوان */
    .header-container {
    display: flex;
    align-items: center; /* توسيط عمودي */
    justify-content: flex-start; /* محاذاة لليسار */
    gap: 20px; /* مسافة بين العناصر */
    padding: 15px;
    background: #ffffff; /* خلفية بيضاء */
    box-shadow: 0 2px 10px rgba(0,0,0,0.1); /* ظل ناعم */
    border-radius: 8px;
    margin-bottom: 30px;
    }
    .logo {
        width: 115px;
        height: auto;
        margin-left: 15px;
    }
    .footer {
        position: fixed;
        bottom: 20px;
        width: 100%;
        text-align: center;
        font-size: 14px;
        color: #333;
    }
    
    
    body {
        background: #f8f9fa !important;
    }
    
    .stTextInput>div>div>input,
    .stNumberInput>div>div>input,
    .stDateInput>div>div>input {
        font-size: 18px !important;
        padding: 12px !important;
    }
    
    .stButton>button {
        width: 100% !important;
        padding: 15px !important;
        font-size: 20px !important;
        background: #007bff !important;
        transition: 0.3s !important;
    }
    
    .stButton>button:hover {
        opacity: 0.9 !important;
        transform: translateY(-2px) !important;
    }
    
    .stFileUploader {
        border: 2px dashed #ced4da !important;
        border-radius: 12px !important;
        padding: 20px !important;
        background: #ffffff !important;
    }
    
    .stFileUploader:hover {
        border-color: #007bff !important;
    }
    
    .stDateInput>div>div>input {
        text-align: right !important;
        direction: rtl !important;
    }
    """
    st.markdown(f"<style>{css_code}</style>", unsafe_allow_html=True)



# تحميل CSS
load_css()


# ---------------------- الإعدادات العامة ----------------------
passwords = ["0102", "1002", "0120", "1314", "2324"]
min_date = datetime.date(1900, 1, 1)
max_date = datetime.date.today()

# ---------------------- الدوال المساعدة ----------------------
def validate_required(fields):
    """التحقق من جميع الحقول الإلزامية"""
    missing = []
    for name, value in fields.items():
        if (isinstance(value, (str, int)) and (not value or (isinstance(value, str) and value.strip() == ""))):
            missing.append(name)
        elif isinstance(value, st.runtime.uploaded_file_manager.UploadedFile) and not value:
            missing.append(name)
        elif value is None:
            missing.append(name)
    return missing



def upload_files(files):
    return [f"file_{i}_link" for i in range(len(files))]

def generate_pdf(data, files):
    return "output.pdf"

# ---------------------- الواجهة الرئيسية ----------------------
st.sidebar.title("التنقل بين الصفحات")
page = st.sidebar.selectbox("اختر الصفحة", [
    "الصفحة الرئيسية",
    "إضافة بيانات الموظفين",
    "إضافة بيانات العقود", 
    "إضافة بيانات العاملين بصفة شراء خدمات"
])

# ---------------------- الصفحة الرئيسية ----------------------
if page == "الصفحة الرئيسية":
    with open("logo.jpg", "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode()
    st.markdown(f"""
        <div style="display: flex; align-items: center; direction: rtl;">
            <img src="data:image/png;base64,{logo_b64}" style="height: 120px; margin-left: 20px;">
            <h1 style="color: #2c3e50;">نظام إدارة بيانات العاملين</h1>
        </div>
    """, unsafe_allow_html=True)

# ---------------------- صفحة الموظفين ----------------------
elif page == "إضافة بيانات الموظفين":
    st.title("إضافة بيانات الموظف")
    password = st.text_input("كلمة المرور *", type="password")
    
    if password in passwords:
        with st.form("employee_form", clear_on_submit=True):
            st.markdown("**جميع الحقول مطلوبة**")
            
            # ------ المعلومات الأساسية ------
            computer_no = st.text_input("رقم الحاسبة *")
            badge_no = st.text_input("رقم الشعار *")
            department = st.text_input("القسم *")
            full_name = st.text_input("الإسم الرباعي واللقب *")
            mother_name = st.text_input("اسم الأم الثلاثي *")
            birth_date = st.date_input("المواليد *", min_value=min_date)
            marital_status = st.selectbox("متزوج *", ["نعم", "لا"])
            
            if marital_status == "نعم":
                marriage_contract = st.file_uploader("ارفاق عقد الزواج *", type=["pdf", "jpg"])
            else:
                marriage_contract = None
                
            family_count = st.number_input("عدد الأفراد *", min_value=0)
            first_child = st.text_input("اول طفل *")
            second_child = st.text_input("ثاني طفل *")
            third_child = st.text_input("ثالث طفل *")
            fourth_child = st.text_input("رابع طفل *")
            address = st.text_input("عنوان السكن *")
            nearby_landmark = st.text_input("أقرب نقطه دالة *")
            appointment_date = st.date_input("تاريخ التعيين *", min_value=min_date)
            administrative_order = st.file_uploader("الامر الاداري للتعيين *", type=["pdf", "jpg"])
            permit_number = st.text_input("رقم التصريح *")
            permit_copy = st.file_uploader("ارفاق نسخة من التصريح *", type=["pdf", "jpg"])
            national_id_front = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الواجهه *", type=["jpg", "png"])
            national_id_back = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الضهر *", type=["jpg", "png"])
            housing_card_front = st.file_uploader("ارفاق نسخة من بطاقه السكن/ الوجه *", type=["jpg", "png"])
            housing_card_back = st.file_uploader("ارفاق نسخة من بطاقه السكن/الضهر *", type=["jpg", "png"])
            mobile = st.text_input("رقم الموبايل *")
            data_entry_name = st.text_input("اسم مدخل البيانات *")

            if st.form_submit_button("حفظ البيانات"):
                required_fields = {
                    "رقم الحاسبة": computer_no,
                    "رقم الشعار": badge_no,
                    "القسم": department,
                    "الإسم الرباعي": full_name,
                    "اسم الأم": mother_name,
                    "عنوان السكن": address,
                    "أقرب نقطه دالة": nearby_landmark,
                    "رقم التصريح": permit_number,
                    "رقم الموبايل": mobile,
                    "اسم مدخل البيانات": data_entry_name,
                    "الامر الاداري": administrative_order,
                    "نسخة التصريح": permit_copy,
                    "البطاقة الوطنية/الواجهه": national_id_front,
                    "البطاقة الوطنية/الضهر": national_id_back,
                    "بطاقة السكن/الوجه": housing_card_front,
                    "بطاقة السكن/الضهر": housing_card_back,
                    "اول طفل": first_child,
                    "ثاني طفل": second_child,
                    "ثالث طفل": third_child,
                    "رابع طفل": fourth_child
                }
                if marital_status == "نعم":
                    required_fields["عقد الزواج"] = marriage_contract
                
                missing = validate_required(required_fields)
                if missing:
                    st.error(f"الحقول الناقصة: {', '.join(missing)}")
                else:
                    try:
                        file_links = upload_files([
                            marriage_contract, administrative_order, permit_copy,
                            national_id_front, national_id_back, housing_card_front,
                            housing_card_back
                        ])
                        st.success("تم الحفظ بنجاح!")
                    except Exception as e:
                        st.error(f"خطأ: {str(e)}")
    
    elif password:
        st.error("كلمة المرور غير صحيحة!")

# ---------------------- صفحة العقود ----------------------
elif page == "إضافة بيانات العقود":
    st.title("إضافة بيانات العقد")
    password = st.text_input("كلمة المرور *", type="password")
    
    if password in passwords:
        with st.form("contract_form", clear_on_submit=True):
            st.markdown("**جميع الحقول مطلوبة**")
            
            computer_no = st.text_input("رقم الحاسبة *")
            badge_no = st.text_input("رقم الشعار *")
            department = st.text_input("القسم *")
            full_name = st.text_input("الإسم الرباعي واللقب *")
            mother_name = st.text_input("اسم الأم الثلاثي *")
            birth_date = st.date_input("المواليد *", min_value=min_date)
            marital_status = st.selectbox("متزوج *", ["نعم", "لا"])
            
            if marital_status == "نعم":
                marriage_contract = st.file_uploader("ارفاق عقد الزواج *", type=["pdf", "jpg"])
            else:
                marriage_contract = None
                
            family_count = st.number_input("عدد الأفراد *", min_value=0)
            first_child = st.text_input("اول طفل *")
            second_child = st.text_input("ثاني طفل *")
            third_child = st.text_input("ثالث طفل *")
            fourth_child = st.text_input("رابع طفل *")
            address = st.text_input("عنوان السكن *")
            nearby_landmark = st.text_input("أقرب نقطه دالة *")
            contract_date = st.date_input("تاريخ التعاقد *", min_value=min_date)
            administrative_order = st.file_uploader("الامر الاداري للتعاقد *", type=["pdf", "jpg"])
            permit_number = st.text_input("رقم التصريح *")
            permit_copy = st.file_uploader("ارفاق نسخة من التصريح *", type=["pdf", "jpg"])
            national_id_front = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الواجهه *", type=["jpg", "png"])
            national_id_back = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الضهر *", type=["jpg", "png"])
            housing_card_front = st.file_uploader("ارفاق نسخة من بطاقه السكن/ الوجه *", type=["jpg", "png"])
            housing_card_back = st.file_uploader("ارفاق نسخة من بطاقه السكن/الضهر *", type=["jpg", "png"])
            mobile = st.text_input("رقم الموبايل *")
            data_entry_name = st.text_input("اسم مدخل البيانات *")

            if st.form_submit_button("حفظ البيانات"):
                required_fields = {
                    "رقم الحاسبة": computer_no,
                    "رقم الشعار": badge_no,
                    "القسم": department,
                    "الإسم الرباعي": full_name,
                    "اسم الأم": mother_name,
                    "عنوان السكن": address,
                    "أقرب نقطه دالة": nearby_landmark,
                    "رقم التصريح": permit_number,
                    "رقم الموبايل": mobile,
                    "اسم مدخل البيانات": data_entry_name,
                    "الامر الاداري": administrative_order,
                    "نسخة التصريح": permit_copy,
                    "البطاقة الوطنية/الواجهه": national_id_front,
                    "البطاقة الوطنية/الضهر": national_id_back,
                    "بطاقة السكن/الوجه": housing_card_front,
                    "بطاقة السكن/الضهر": housing_card_back,
                    "اول طفل": first_child,
                    "ثاني طفل": second_child,
                    "ثالث طفل": third_child,
                    "رابع طفل": fourth_child
                }
                if marital_status == "نعم":
                    required_fields["عقد الزواج"] = marriage_contract
                
                missing = validate_required(required_fields)
                if missing:
                    st.error(f"الحقول الناقصة: {', '.join(missing)}")
                else:
                    try:
                        file_links = upload_files([
                            marriage_contract, administrative_order, permit_copy,
                            national_id_front, national_id_back, housing_card_front,
                            housing_card_back
                        ])
                        st.success("تم الحفظ بنجاح!")
                    except Exception as e:
                        st.error(f"خطأ: {str(e)}")
    
    elif password:
        st.error("كلمة المرور غير صحيحة!")

# ---------------------- صفحة شراء الخدمات ----------------------
elif page == "إضافة بيانات العاملين بصفة شراء خدمات":
    st.title("إضافة بيانات العاملين بصفة شراء خدمات")
    password = st.text_input("كلمة المرور *", type="password")
    
    if password in passwords:
        with st.form("service_form", clear_on_submit=True):
            st.markdown("**جميع الحقول مطلوبة**")
            
            computer_no = st.text_input("رقم الحاسبة *")
            department = st.text_input("القسم *")
            full_name = st.text_input("الإسم الرباعي واللقب *")
            mother_name = st.text_input("اسم الأم الثلاثي *")
            birth_date = st.date_input("المواليد *", min_value=min_date)
            address = st.text_input("عنوان السكن *")
            nearby_landmark = st.text_input("أقرب نقطه دالة *")
            referral_date = st.date_input("تاريخ الإحالة *", min_value=min_date)
            referral_duration = st.number_input("مدة الإحالة *", min_value=1)
            referral_copy = st.file_uploader("ارفاق نسخة من الإحالة *", type=["pdf", "jpg"])
            permit_number = st.text_input("رقم التصريح *")
            permit_copy = st.file_uploader("ارفاق نسخة من التصريح *", type=["pdf", "jpg"])
            national_id_front = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الواجهه *", type=["jpg", "png"])
            national_id_back = st.file_uploader("ارفاق نسخة من البطاقة الوطنية/الضهر *", type=["jpg", "png"])
            housing_card_front = st.file_uploader("ارفاق نسخة من بطاقه السكن/ الوجه *", type=["jpg", "png"])
            housing_card_back = st.file_uploader("ارفاق نسخة من بطاقه السكن/الضهر *", type=["jpg", "png"])
            mobile = st.text_input("رقم الموبايل *")
            data_entry_name = st.text_input("اسم مدخل البيانات *")

            if st.form_submit_button("حفظ البيانات"):
                required_fields = {
                    "رقم الحاسبة": computer_no,
                    "القسم": department,
                    "الإسم الرباعي": full_name,
                    "اسم الأم": mother_name,
                    "عنوان السكن": address,
                    "أقرب نقطه دالة": nearby_landmark,
                    "رقم التصريح": permit_number,
                    "رقم الموبايل": mobile,
                    "اسم مدخل البيانات": data_entry_name,
                    "نسخة الإحالة": referral_copy,
                    "نسخة التصريح": permit_copy,
                    "البطاقة الوطنية/الواجهه": national_id_front,
                    "البطاقة الوطنية/الضهر": national_id_back,
                    "بطاقة السكن/الوجه": housing_card_front,
                    "بطاقة السكن/الضهر": housing_card_back
                }
                
                missing = validate_required(required_fields)
                if missing:
                    st.error(f"الحقول الناقصة: {', '.join(missing)}")
                else:
                    try:
                        file_links = upload_files([
                            referral_copy, permit_copy, 
                            national_id_front, national_id_back,
                            housing_card_front, housing_card_back
                        ])
                        st.success("تم الحفظ بنجاح!")
                    except Exception as e:
                        st.error(f"خطأ: {str(e)}")
    
    elif password:
        st.error("كلمة المرور غير صحيحة!")
