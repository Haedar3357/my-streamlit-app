import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import tempfile
import base64
import datetime

# تحديد تاريخ أدنى وحد أقصى
min_date = datetime.date(1900, 1, 1)
max_date = datetime.date.today()

# إعداد الاتصال بـ Google Sheets و Google Drive
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

# بناء بيانات الاعتماد من secrets
secret = st.secrets["gcp_service_account"]
credentials_info = {
    "type": secret["type"],
    "project_id": secret["project_id"],
    "private_key_id": secret["private_key_id"],
    "private_key": secret["private_key"].replace("\n", "\\n"),  # تأكد من استبدال علامات نهاية الأسطر
    "client_email": secret["client_email"],
    "client_id": secret["client_id"],
    "auth_uri": secret["auth_uri"],
    "token_uri": secret["token_uri"],
    "auth_provider_x509_cert_url": secret["auth_provider_x509_cert_url"],
    "client_x509_cert_url": secret["client_x509_cert_url"]
}

# إنشاء كائن من بيانات الاعتماد
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_info, scope)
gc = gspread.authorize(credentials)

# فتح ملفات Google Sheet لكل قسم
sh_employees = gc.open("بيانات الموظفين")
sh_contracts = gc.open("بيانات العقود")
sh_service = gc.open("بيانات الخدمة")

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
    else:
        if user_password:  # فقط إظهار الرسالة إذا كانت هناك محاولة إدخال كلمة سر
            st.error("كلمة السر غير صحيحة. يرجى المحاولة مرة أخرى.")
elif page == "إضافة خدمة":
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
                address, nearby_landmark, str(referral_date), referral_duration, 
                file_links[0], permit_number, file_links[1], file_links[2], 
                file_links[3], file_links[4], file_links[5], mobile, data_entry_name
            ])
            
            st.success("تم حفظ البيانات بنجاح!")
    else:
        if user_password:  # فقط إظهار الرسالة إذا كانت هناك محاولة إدخال كلمة سر
            st.error("كلمة السر غير صحيحة. يرجى المحاولة مرة أخرى.")

st.markdown("<div class='footer'>تم أعداد وتصميم الاستمارة<br>Ali.H.gma</div>", unsafe_allow_html=True)
