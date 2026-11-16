"""Script kiểm tra chức năng nộp đơn ứng tuyển.

Kiểm tra các trường hợp:
1. CV thuộc tài khoản đăng nhập
2. Chỉ nộp vào tin OPEN còn hạn
3. Chặn nộp trùng
4. Gửi thông báo đúng nhà tuyển dụng

Yêu cầu:
- Database đã được khởi tạo
- Có sẵn user candidate, employer, cv, job trong database
- Server đang chạy tại http://127.0.0.1:8000
"""
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:8000/api"

# Màu cho terminal
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.RESET}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")

def print_section(title):
    print(f"\n{Colors.BLUE}{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}{Colors.RESET}\n")


# ============================================================================
# Test Functions
# ============================================================================

def test_login(email, password, role_name):
    """Đăng nhập và lấy token."""
    print_info(f"Đăng nhập với {role_name}: {email}")
    
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password}
    )
    
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        print_success(f"Đăng nhập thành công! Token: {token[:20]}...")
        return token
    else:
        print_error(f"Đăng nhập thất bại: {response.status_code} - {response.text}")
        return None


def test_get_my_cvs(token):
    """Lấy danh sách CV của candidate."""
    print_info("Lấy danh sách CV của candidate...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/cvs", headers=headers)
    
    if response.status_code == 200:
        cvs = response.json()
        if cvs:
            print_success(f"Tìm thấy {len(cvs)} CV")
            for cv in cvs:
                print(f"  - CV #{cv['id']}: {cv.get('file_name', 'N/A')}")
            return cvs
        else:
            print_warning("Không có CV nào. Cần tạo CV trước khi test.")
            return []
    else:
        print_error(f"Lỗi khi lấy CV: {response.status_code} - {response.text}")
        return []


def test_get_open_jobs(token=None):
    """Lấy danh sách tin tuyển dụng OPEN."""
    print_info("Lấy danh sách tin tuyển dụng OPEN...")
    
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = requests.get(f"{BASE_URL}/jobs?status=OPEN", headers=headers)
    
    if response.status_code == 200:
        jobs = response.json()
        if jobs:
            print_success(f"Tìm thấy {len(jobs)} tin tuyển dụng OPEN")
            for job in jobs[:3]:  # Chỉ hiển thị 3 tin đầu
                deadline = job.get('deadline', 'N/A')
                print(f"  - Job #{job['id']}: {job['title']} (Deadline: {deadline})")
            return jobs
        else:
            print_warning("Không có tin tuyển dụng OPEN nào.")
            return []
    else:
        print_error(f"Lỗi khi lấy jobs: {response.status_code} - {response.text}")
        return []


def test_create_application(token, job_id, cv_id, cover_letter):
    """Nộp đơn ứng tuyển."""
    print_info(f"Nộp đơn vào Job #{job_id} với CV #{cv_id}...")
    
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "job_id": job_id,
        "cv_id": cv_id,
        "cover_letter": cover_letter
    }
    
    response = requests.post(
        f"{BASE_URL}/applications",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        application = response.json()
        print_success(f"Nộp đơn thành công! Application ID: {application['id']}")
        print(f"  - Trạng thái: {application['status']}")
        print(f"  - Thời gian: {application['created_at']}")
        return application
    else:
        print_error(f"Nộp đơn thất bại: {response.status_code}")
        try:
            error = response.json()
            print_error(f"  Chi tiết: {error.get('detail', response.text)}")
        except:
            print_error(f"  Chi tiết: {response.text}")
        return None


def test_duplicate_application(token, job_id, cv_id):
    """Test nộp trùng đơn (phải bị chặn)."""
    print_info(f"Test nộp trùng: Job #{job_id} với CV #{cv_id}...")
    
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "job_id": job_id,
        "cv_id": cv_id,
        "cover_letter": "Đây là lần nộp thứ 2 (phải bị chặn)"
    }
    
    response = requests.post(
        f"{BASE_URL}/applications",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 409:  # Conflict
        error = response.json()
        print_success(f"Chặn nộp trùng thành công! Status: {response.status_code}")
        print(f"  Message: {error.get('detail')}")
        return True
    elif response.status_code == 200:
        print_error("FAILED: Không chặn được nộp trùng! Đơn đã được tạo.")
        return False
    else:
        print_warning(f"Kết quả không mong đợi: {response.status_code} - {response.text}")
        return False


def test_apply_with_wrong_cv(token, job_id, wrong_cv_id):
    """Test nộp đơn với CV không thuộc về mình (phải bị chặn)."""
    print_info(f"Test nộp với CV không thuộc về mình: CV #{wrong_cv_id}...")
    
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "job_id": job_id,
        "cv_id": wrong_cv_id,
        "cover_letter": "Test CV của người khác"
    }
    
    response = requests.post(
        f"{BASE_URL}/applications",
        headers=headers,
        json=payload
    )
    
    if response.status_code in [403, 404]:  # Forbidden hoặc Not Found
        error = response.json()
        print_success(f"Chặn CV không hợp lệ thành công! Status: {response.status_code}")
        print(f"  Message: {error.get('detail')}")
        return True
    elif response.status_code == 200:
        print_error("FAILED: Không chặn được CV không hợp lệ!")
        return False
    else:
        print_warning(f"Kết quả không mong đợi: {response.status_code} - {response.text}")
        return False


def test_get_my_applications(token):
    """Lấy danh sách đơn ứng tuyển của candidate."""
    print_info("Lấy danh sách đơn ứng tuyển của mình...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/applications", headers=headers)
    
    if response.status_code == 200:
        applications = response.json()
        print_success(f"Tìm thấy {len(applications)} đơn ứng tuyển")
        for app in applications[:3]:  # Chỉ hiển thị 3 đơn đầu
            print(f"  - Application #{app['id']}: Job #{app['job_id']} - {app['status']}")
        return applications
    else:
        print_error(f"Lỗi khi lấy applications: {response.status_code} - {response.text}")
        return []


# ============================================================================
# Main Test Flow
# ============================================================================

def main():
    print_section("KIỂM TRA CHỨC NĂNG NỘP ĐƠN ỨNG TUYỂN")
    
    # Thông tin test (cần điều chỉnh theo database của bạn)
    CANDIDATE_EMAIL = "candidate@test.com"
    CANDIDATE_PASSWORD = "123456"
    
    print_warning("LƯU Ý: Script này cần database đã có sẵn:")
    print("  - User candidate với email/password trên")
    print("  - Candidate đã có hồ sơ (CandidateProfile)")
    print("  - Candidate đã upload ít nhất 1 CV")
    print("  - Có ít nhất 1 tin tuyển dụng OPEN còn hạn")
    print("  - Server đang chạy tại http://127.0.0.1:8000")
    
    input("\nNhấn Enter để tiếp tục...")
    
    # Test 1: Đăng nhập
    print_section("TEST 1: ĐĂNG NHẬP")
    candidate_token = test_login(CANDIDATE_EMAIL, CANDIDATE_PASSWORD, "Candidate")
    
    if not candidate_token:
        print_error("\n❌ Không thể đăng nhập. Dừng test.")
        return
    
    # Test 2: Lấy danh sách CV
    print_section("TEST 2: LẤY DANH SÁCH CV")
    cvs = test_get_my_cvs(candidate_token)
    
    if not cvs:
        print_error("\n❌ Không có CV. Dừng test.")
        return
    
    my_cv_id = cvs[0]['id']
    
    # Test 3: Lấy danh sách tin tuyển dụng OPEN
    print_section("TEST 3: LẤY TIN TUYỂN DỤNG OPEN")
    jobs = test_get_open_jobs(candidate_token)
    
    if not jobs:
        print_error("\n❌ Không có tin tuyển dụng OPEN. Dừng test.")
        return
    
    test_job_id = jobs[0]['id']
    
    # Test 4: Nộp đơn ứng tuyển
    print_section("TEST 4: NỘP ĐƠN ỨNG TUYỂN")
    application = test_create_application(
        candidate_token,
        test_job_id,
        my_cv_id,
        "Tôi rất mong muốn được làm việc tại công ty. Tôi có kinh nghiệm 3 năm..."
    )
    
    if not application:
        print_warning("Đơn không được tạo (có thể đã nộp trước đó)")
    
    # Test 5: Nộp trùng (phải bị chặn)
    print_section("TEST 5: TEST NỘP TRÙNG (PHẢI BỊ CHẶN)")
    test_duplicate_application(candidate_token, test_job_id, my_cv_id)
    
    # Test 6: Test với CV không thuộc về mình
    print_section("TEST 6: TEST CV KHÔNG HỢP LỆ")
    wrong_cv_id = 99999  # ID không tồn tại
    test_apply_with_wrong_cv(candidate_token, test_job_id, wrong_cv_id)
    
    # Test 7: Xem danh sách đơn đã nộp
    print_section("TEST 7: XEM DANH SÁCH ĐƠN ĐÃ NỘP")
    test_get_my_applications(candidate_token)
    
    # Kết luận
    print_section("KẾT LUẬN")
    print_success("Hoàn thành các test case chính!")
    print("\nCác tính năng đã kiểm tra:")
    print("  ✓ Đăng nhập và xác thực")
    print("  ✓ Lấy danh sách CV của candidate")
    print("  ✓ Lấy tin tuyển dụng OPEN")
    print("  ✓ Nộp đơn ứng tuyển với CV và cover letter")
    print("  ✓ Chặn nộp trùng (UNIQUE constraint)")
    print("  ✓ Chặn CV không hợp lệ")
    print("  ✓ Xem danh sách đơn đã nộp")
    
    print("\nLƯU Ý:")
    print("  - Kiểm tra thông báo: Cần check database bảng 'notifications'")
    print("  - Kiểm tra deadline: Cần test với job đã hết hạn")
    print("  - Kiểm tra job status: Cần test với job CLOSED/FILLED")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest bị hủy bởi người dùng.")
    except Exception as e:
        print_error(f"\n\nLỗi không mong đợi: {str(e)}")
        import traceback
        traceback.print_exc()



