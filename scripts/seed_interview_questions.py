"""Script seed 45 câu hỏi phỏng vấn IT cho bảng interview_questions.
Tuân thủ techrecruit-rules: dữ liệu chuẩn, không sao chép TopCV, không có tiền tố [Seed].
"""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from dotenv import load_dotenv; load_dotenv()
from app.db.session import engine
from sqlalchemy import text

QUESTIONS = [
    # Category 1: Backend & API (id=1)
    {
        "category_id": 1, "level_id": 1, # Intern
        "question": "RESTful API là gì và phân biệt các phương thức GET, POST, PUT, DELETE?",
        "answer_hint": "REST (Representational State Transfer) là kiến trúc định hình giao tiếp giữa client và server dựa trên HTTP chuẩn. Phân biệt: GET dùng lấy dữ liệu (idempotent, an toàn, có cache); POST tạo mới tài nguyên (không idempotent); PUT thay thế toàn bộ tài nguyên theo URI (idempotent); DELETE xóa tài nguyên (idempotent). Chú ý sử dụng đúng HTTP status codes (200, 201, 204, 400, 404, 500)."
    },
    {
        "category_id": 1, "level_id": 2, # Fresher
        "question": "Trình bày sự khác biệt giữa Cookie-based Session và JSON Web Token (JWT)?",
        "answer_hint": "Cookie-based Session lưu trạng thái trên server (bộ nhớ hoặc Redis), client giữ session ID trong cookie (Stateful). Dễ thu hồi quyền tức thì nhưng tốn tài nguyên server khi mở rộng. JWT lưu thông tin đã ký điện tử (header.payload.signature) ngay tại token trên client (Stateless), giúp hệ thống phân tán scale dễ dàng. Nhược điểm của JWT là kích thước payload lớn hơn và khó thu hồi trước khi hết hạn (cần blacklist token)."
    },
    {
        "category_id": 1, "level_id": 3, # Junior
        "question": "Nêu các kỹ thuật tối ưu hóa truy vấn SQL khi bảng có hàng triệu bản ghi?",
        "answer_hint": "1. Đánh index hợp lý (B-Tree index trên các cột WHERE/JOIN/ORDER BY, tránh đánh index dư thừa). 2. Phân tích kế hoạch thực thi bằng EXPLAIN để phát hiện Full Table Scan. 3. Chỉ SELECT các cột cần thiết, tránh SELECT *. 4. Tránh dùng hàm hoặc biểu thức trên cột có index (ví dụ WHERE YEAR(date)=2026 sẽ vô hiệu hóa index). 5. Sử dụng phân trang theo con trỏ (keyset pagination) thay vì OFFSET lớn."
    },
    {
        "category_id": 1, "level_id": 3, # Junior
        "question": "Connection pooling trong cơ sở dữ liệu hoạt động như thế nào và vì sao cần sử dụng?",
        "answer_hint": "Tạo kết nối TCP mới và xác thực handshake với database tốn nhiều chi phí tài nguyên và độ trễ. Connection pool duy trì sẵn một tập hợp kết nối hoạt động; khi request đến sẽ mượn kết nối từ pool và trả lại sau khi hoàn thành truy vấn. Cần cấu hình max_connections, timeout và connection validation hợp lý để tránh kiệt tài nguyên pool hoặc nghẽn thread."
    },
    {
        "category_id": 1, "level_id": 4, # Middle
        "question": "Giải thích cơ chế Transaction Isolation Levels trong cơ sở dữ liệu và hiện tượng Phantom Read?",
        "answer_hint": "ANSI SQL định nghĩa 4 mức cô lập: Read Uncommitted (cho phép Dirty Read), Read Committed (ngăn Dirty Read, bị Non-repeatable Read), Repeatable Read (ngăn Non-repeatable Read, có thể bị Phantom Read ở một số DB), và Serializable (cô lập hoàn toàn). Phantom Read xảy ra khi transaction A đọc tập bản ghi theo điều kiện, transaction B INSERT bản ghi mới thỏa điều kiện và COMMIT, transaction A đọc lại thấy xuất hiện bản ghi 'bóng ma'."
    },
    {
        "category_id": 1, "level_id": 4, # Middle
        "question": "Phân biệt Optimistic Locking và Pessimistic Locking, khi nào nên chọn phương án nào?",
        "answer_hint": "Pessimistic Locking khóa bản ghi ngay khi đọc (SELECT ... FOR UPDATE), ngăn chặn mọi giao dịch khác can thiệp; phù hợp khi tỷ lệ xung đột cao (giao dịch tài chính, giữ chỗ vé). Optimistic Locking không khóa dữ liệu khi đọc mà kiểm tra trường version/timestamp lúc UPDATE; phù hợp khi lưu lượng đọc nhiều hơn ghi và tỷ lệ xung đột thấp, giúp tăng thông lượng xử lý."
    },
    {
        "category_id": 1, "level_id": 4, # Middle
        "question": "Kỹ thuật xử lý Idempotency trong REST API đối với các tác vụ tạo đơn hàng hoặc thanh toán?",
        "answer_hint": "Client sinh Idempotency-Key duy nhất (UUID v4) gửi trong header HTTP. Khi request đến, server lưu key vào Redis/Database với trạng thái 'PENDING'. Nếu có request thứ hai cùng key tới trong lúc xử lý, server từ chối hoặc yêu cầu đợi. Sau khi giao dịch xong, server lưu kết quả vào cache. Mọi request lặp lại cùng key sẽ nhận lại đúng kết quả đã lưu mà không thực hiện lại logic giao dịch."
    },
    {
        "category_id": 1, "level_id": 5, # Senior
        "question": "Làm thế nào để thiết kế giải pháp Cache Invalidation hiệu quả (Cache-Aside, Write-Through, Write-Behind)?",
        "answer_hint": "Cache-Aside: Ứng dụng tự đọc cache, nếu cache miss thì đọc DB rồi ghi vào cache; khi ghi dữ liệu thì xóa cache (xóa an toàn hơn ghi đè để tránh race condition). Write-Through: Ghi đồng thời vào cache và database. Write-Behind (Write-Back): Ghi vào cache trước, bất đồng bộ ghi DB (tốc độ cao nhưng rủi ro mất dữ liệu nếu cache crash). Cần kết hợp TTL hợp lý và cơ chế distributed lock để chống Cache Avalanche và Cache Stampede."
    },
    {
        "category_id": 1, "level_id": 5, # Senior
        "question": "Mô hình Saga Pattern trong Microservices giải quyết bài toán phân tán dữ liệu như thế nào?",
        "answer_hint": "Saga thay thế 2-Phase Commit (2PC) bằng một chuỗi các local transactions. Mỗi transaction cập nhật DB nội bộ và phát sự kiện trigger bước tiếp theo. Nếu một bước thất bại, Saga kích hoạt chuỗi Compensating Transactions (giao dịch bù trừ) để khôi phục trạng thái nhất quán cuối cùng (Eventual Consistency). Triển khai theo 2 cách: Choreography (hướng sự kiện phân tán) hoặc Orchestration (bộ điều phối trung tâm quản lý luồng trạng thái)."
    },
    {
        "category_id": 1, "level_id": 6, # Lead
        "question": "Chiến lược thiết kế Zero-Downtime Migration cho cơ sở dữ liệu có dung lượng lớn và lưu lượng truy cập cao?",
        "answer_hint": "Áp dụng phương pháp Expand and Contract (Parallel Run): Bước 1: Thêm cột/bảng mới, không sửa code cũ. Bước 2: Deploy code mới có khả năng đọc cột cũ nhưng ghi song song vào cả cột cũ và mới (Dual-Write). Bước 3: Chạy background worker chuyển đổi (backfill) dữ liệu cũ sang mới theo batch nhỏ. Bước 4: Chuyển code sang đọc cột mới hoàn toàn. Bước 5: Ngừng Dual-Write và xóa cột cũ (Contract). Không khóa bảng trong suốt quá trình."
    },

    # Category 2: Frontend & UI/UX (id=2)
    {
        "category_id": 2, "level_id": 1, # Intern
        "question": "Phân biệt CSS Box Model: content-box và border-box ảnh hưởng thế nào đến kích thước phần tử?",
        "answer_hint": "Trong content-box (mặc định), chiều rộng (width) và chiều cao (height) chỉ tính phần nội dung; padding và border sẽ cộng thêm vào kích thước tổng của phần tử. Trong border-box (khuyến nghị qua box-sizing: border-box), width và height đã bao gồm cả padding và border, giúp việc bố cục giao diện responsive chính xác và dễ dự đoán hơn."
    },
    {
        "category_id": 2, "level_id": 2, # Fresher
        "question": "Event Loop trong JavaScript hoạt động như thế nào? Phân biệt Microtask và Macrotask?",
        "answer_hint": "JavaScript là đơn luồng (single-threaded). Call Stack thực thi code đồng bộ. Các tác vụ bất đồng bộ được đưa vào Callback Queues. Event Loop liên tục kiểm tra nếu Call Stack rỗng sẽ ưu tiên lấy toàn bộ tác vụ trong Microtask Queue (Promise callbacks, queueMicrotask, MutationObserver) ra chạy trước, sau đó mới lấy 1 tác vụ từ Macrotask Queue (setTimeout, setInterval, I/O, UI rendering)."
    },
    {
        "category_id": 2, "level_id": 2, # Fresher
        "question": "So sánh CSS Flexbox và CSS Grid: khi nào nên ưu tiên Flexbox, khi nào nên dùng Grid?",
        "answer_hint": "Flexbox thiết kế cho bố cục một chiều (1D - hoặc theo hàng row hoặc theo cột column), tối ưu cho căn chỉnh nội dung, thanh điều hướng, thẻ tag hoặc các nhóm phần tử linh hoạt. CSS Grid thiết kế cho bố cục hai chiều (2D - cả hàng và cột đồng thời), tối ưu cho layout tổng thể trang, lưới thẻ sản phẩm có cấu trúc chặt chẽ và responsive phức tạp."
    },
    {
        "category_id": 2, "level_id": 3, # Junior
        "question": "Giải thích cơ chế Virtual DOM và thuật toán Diffing trong các thư viện UI hiện đại?",
        "answer_hint": "Virtual DOM là biểu diễn cấu trúc cây nhẹ bằng JavaScript object phản ánh DOM thật. Khi state thay đổi, render cycle tạo ra Virtual DOM tree mới. Thuật toán Diffing so sánh cây mới và cũ với độ phức tạp O(n) nhờ các giả định: hai phần tử khác kiểu (type) sẽ sinh ra cây khác nhau, và các phần tử con trong mảng cần có thuộc tính 'key' ổn định để nhận diện vị trí. Sau đó chỉ cập nhật các thay đổi thực sự lên real DOM (Reconciliation)."
    },
    {
        "category_id": 2, "level_id": 3, # Junior
        "question": "Làm thế nào để cải thiện điểm Core Web Vitals (LCP, FID/INP, CLS) trên ứng dụng web?",
        "answer_hint": "LCP (Largest Contentful Paint): Tối ưu hình ảnh (WebP/AVIF, responsive srcset, fetchpriority='high'), dùng CDN, nén tài nguyên và SSR/SSG. INP (Interaction to Next Paint): Giảm long tasks trên main thread (>50ms), tách công việc với scheduler.yield() hoặc Web Worker. CLS (Cumulative Layout Shift): Luôn khai báo explicit width/height hoặc aspect-ratio cho ảnh/video, dự trữ khoảng trống cho ads và font loading font-display: optional."
    },
    {
        "category_id": 2, "level_id": 4, # Middle
        "question": "So sánh Client-Side Rendering (CSR), Server-Side Rendering (SSR) và Static Site Generation (SSG)?",
        "answer_hint": "CSR: Trình duyệt tải HTML rỗng và file JS lớn, render giao diện phía client; chuyển trang mượt nhưng FCP chậm và SEO khó hơn. SSR: Server sinh HTML kèm dữ liệu cho mỗi request; SEO tốt, FCP nhanh nhưng tăng tải CPU server và TTFB phụ thuộc tốc độ backend. SSG: Tạo sẵn toàn bộ file HTML tĩnh lúc build; tốc độ truy xuất cực nhanh qua CDN, chi phí thấp, tối ưu cho trang blog/tài liệu ít biến động."
    },
    {
        "category_id": 2, "level_id": 4, # Middle
        "question": "Trình bày các phương pháp quản lý trạng thái phức tạp và cách tránh re-render không cần thiết?",
        "answer_hint": "Nguyên tắc: Colocate state gần nơi sử dụng nhất có thể. Dùng kỹ thuật State Lifting khi nhiều component cần chung dữ liệu. Để tránh re-render lãng phí: 1. Tách nhỏ component độc lập. 2. Memoization hợp lý (React.memo, useMemo, useCallback) kèm profiling đo lường. 3. Sử dụng atomic state (Zustand, Recoil) hoặc fine-grained reactivity (Signals) để chỉ re-render đúng node phụ thuộc thay vì cả cây component."
    },
    {
        "category_id": 2, "level_id": 5, # Senior
        "question": "Kiến trúc Micro-frontends là gì? Những thách thức về chia sẻ dependency, định tuyến và styled isolation?",
        "answer_hint": "Micro-frontends chia nhỏ monolith frontend thành các ứng dụng độc lập do các squad tự chủ phát triển và deploy. Thách thức: 1. Dependency sharing: Dùng Module Federation (Webpack/Vite) với shared singleton (React, design tokens) để tránh tải thư viện lặp lại. 2. Routing: Shell container điều phối URL và đồng bộ history. 3. CSS Isolation: Dùng Shadow DOM, CSS Modules hoặc scoped namespaces để tránh xung đột CSS toàn cục."
    },
    {
        "category_id": 2, "level_id": 6, # Lead
        "question": "Quy trình xây dựng Design System và kiểm thử khả năng truy cập (Accessibility WCAG 2.1 AA)?",
        "answer_hint": "1. Thiết lập Design Tokens chuẩn (Color, Typography, Spacing, Elevation, Motion) đồng bộ giữa Figma và Code. 2. Xây dựng Headless/Accessible primitives hỗ trợ bàn phím (Tab, Arrow keys, Esc), focus trap cho modal, ARIA roles & attributes đầy đủ. 3. Độ tương phản màu sắc đạt tối thiểu 4.5:1 cho text thường. 4. Tích hợp tự động axe-core linter và CI tests, kết hợp kiểm thử thực tế với Screen Reader (NVDA, VoiceOver)."
    },

    # Category 3: AI & Data Science (id=3)
    {
        "category_id": 3, "level_id": 2, # Fresher
        "question": "Phân biệt Supervised Learning, Unsupervised Learning và Reinforcement Learning?",
        "answer_hint": "Supervised Learning (Học có giám sát): Huấn luyện trên dữ liệu có nhãn (X, y); ví dụ dự đoán giá nhà (Regression) hoặc phân loại thư rác (Classification). Unsupervised Learning (Học không giám sát): Tìm cấu trúc/mô hình ẩn từ dữ liệu không nhãn; ví dụ phân cụm khách hàng K-means hoặc giảm số chiều PCA. Reinforcement Learning (Học tăng cường): Agent học thông qua tương tác với môi trường để tối đa hóa điểm thưởng (reward); ví dụ AlphaGo hoặc điều khiển robot."
    },
    {
        "category_id": 3, "level_id": 3, # Junior
        "question": "Hiện tượng Overfitting và Underfitting là gì? Các kỹ thuật phổ biến để khắc phục Overfitting?",
        "answer_hint": "Underfitting: Mô hình quá đơn giản, không học được quy luật dữ liệu (High Bias, Low Variance). Overfitting: Mô hình học quá kỹ cả nhiễu của tập train, khái quát hóa kém trên tập test (Low Bias, High Variance). Khắc phục Overfitting: 1. Thu thập thêm dữ liệu hoặc Data Augmentation. 2. Sử dụng Regularization (L1 Lasso, L2 Ridge, Dropout trong Deep Learning). 3. Early Stopping trong quá trình huấn luyện. 4. Giảm bớt số chiều đặc trưng hoặc độ phức tạp của mô hình."
    },
    {
        "category_id": 3, "level_id": 3, # Junior
        "question": "Giải thích các chỉ số đánh giá mô hình phân loại: Precision, Recall, F1-score và ROC-AUC?",
        "answer_hint": "Precision = TP / (TP + FP): Độ chính xác khi mô hình dự đoán dương tính. Recall = TP / (TP + FN): Tỷ lệ phát hiện được các mẫu dương tính thực tế. F1-score là trung bình điều hòa của Precision và Recall, rất quan trọng khi dữ liệu bị mất cân bằng (imbalanced data). ROC-AUC đo lường khả năng phân biệt giữa các lớp ở mọi ngưỡng threshold, giá trị từ 0.5 (ngẫu nhiên) đến 1.0 (hoàn hảo)."
    },
    {
        "category_id": 3, "level_id": 4, # Middle
        "question": "Kiến trúc Transformer hoạt động ra sao và cơ chế Self-Attention mang lại đột phá gì?",
        "answer_hint": "Transformer loại bỏ tính tuần tự của RNN/LSTM, cho phép tính toán song song toàn bộ chuỗi đầu vào. Cơ chế Scaled Dot-Product Attention tính toán ma trận Attention: softmax(Q * K^T / sqrt(d_k)) * V. Mỗi từ có thể liên kết trực tiếp với mọi từ khác trong câu bất kể khoảng cách ngữ cảnh (giải quyết triệt để vấn đề vanishing gradient của RNN). Kết hợp Positional Encoding và Multi-Head Attention giúp nắm bắt đa dạng các góc độ ngữ nghĩa."
    },
    {
        "category_id": 3, "level_id": 4, # Middle
        "question": "Quy trình triển khai RAG (Retrieval-Augmented Generation) kết hợp Vector Database và LLM?",
        "answer_hint": "Quy trình gồm 2 pha: Ingestion và Retrieval-Generation. 1. Ingestion: Thu thập tài liệu, cắt chunk hợp lý (Chunking strategy kèm overlap), sinh vector nhúng (Embedding) và lưu vào Vector DB (Milvus, Qdrant, Chroma). 2. Retrieval: Khi user hỏi, query được embed và tìm kiếm tương đồng vector (Cosine similarity) kết hợp Hybrid Search (BM25 + Dense vector) và Reranker. 3. Generation: Đưa tài liệu liên quan vào context window của LLM để sinh câu trả lời chính xác, tránh ảo giác (hallucination)."
    },
    {
        "category_id": 3, "level_id": 5, # Senior
        "question": "Chiến lược tối ưu chi phí và độ trễ khi phục vụ (serving) mô hình ngôn ngữ lớn (LLM)?",
        "answer_hint": "1. Kỹ thuật lượng tử hóa (Quantization): AWQ, GPTQ, GGUF giảm trọng số từ FP16 xuống INT8/INT4 giúp tiết kiệm VRAM và tăng tốc inference. 2. PagedAttention và Continuous Batching (vLLM, TensorRT-LLM) tối ưu quản lý KV-cache bộ nhớ. 3. Speculative Decoding: Dùng mô hình nhỏ tạo trước token dự kiến để mô hình lớn xác thực song song. 4. Semantic Caching (Redis/GPTCache) tái sử dụng kết quả cho các câu hỏi tương tự."
    },
    {
        "category_id": 3, "level_id": 5, # Senior
        "question": "Xây dựng MLOps pipeline tự động hóa và phát hiện Data Drift / Concept Drift?",
        "answer_hint": "Pipeline gồm: Data Versioning (DVC), Model Registry (MLflow), Automated Retraining (Kubeflow/Airflow), và Continuous Monitoring (EvidentlyAI). Data Drift xảy ra khi phân phối đầu vào P(X) thay đổi (đo bằng KS-test hoặc Wasserstein Distance); Concept Drift xảy ra khi mối quan hệ giữa đầu vào và mục tiêu P(Y|X) thay đổi. Khi metric vượt ngưỡng cảnh báo, hệ thống tự động kích hoạt pipeline thu thập dữ liệu mới và huấn luyện lại mô hình."
    },

    # Category 4: DevOps & Cloud (id=4)
    {
        "category_id": 4, "level_id": 3, # Junior
        "question": "Docker Container khác với Virtual Machine (máy ảo) như thế nào về mặt kiến trúc và hiệu năng?",
        "answer_hint": "Virtual Machine chạy trên Hypervisor (Type 1 hoặc 2), mỗi máy ảo có một Guest OS riêng hoàn chỉnh, tốn gigabyte dung lượng đĩa và khởi động trong vài phút. Docker Container chia sẻ chung Linux Kernel của Host OS, cô lập tài nguyên qua cgroups và namespaces, chỉ đóng gói ứng dụng và thư viện phụ thuộc; khởi động trong vài giây và tiêu thụ RAM cực ít."
    },
    {
        "category_id": 4, "level_id": 3, # Junior
        "question": "Giải thích các thành phần cơ bản trong Kubernetes: Pod, Service, Deployment, Ingress?",
        "answer_hint": "Pod là đơn vị nhỏ nhất, chứa 1 hoặc nhiều container chia sẻ chung network namespace và storage. Deployment quản lý vòng đời và số lượng replica của Pods (declarative updates, rollback). Service cung cấp địa chỉ IP ổn định và cân bằng tải nội bộ giữa các Pods. Ingress hoạt động ở Layer 7 (HTTP/HTTPS), định tuyến lưu lượng từ bên ngoài internet vào các Service nội bộ theo hostname hoặc path."
    },
    {
        "category_id": 4, "level_id": 4, # Middle
        "question": "Multi-stage build trong Dockerfile giúp tối ưu kích thước image và tính bảo mật như thế nào?",
        "answer_hint": "Multi-stage build tách Dockerfile thành nhiều giai đoạn (stages) có các FROM riêng biệt. Giai đoạn builder chứa đầy đủ SDK, compiler và source code để build artifact (ví dụ binary Go hoặc bundle JS). Giai đoạn runtime cuối cùng chỉ copy đúng file artifact từ builder sang base image siêu nhẹ (Alpine hoặc Distroless). Kết quả: image giảm kích thước từ hàng gigabyte xuống vài chục megabyte và loại bỏ hoàn toàn compiler/source code khỏi môi trường production, giảm thiểu bề mặt tấn công."
    },
    {
        "category_id": 4, "level_id": 4, # Middle
        "question": "Phân biệt các chiến lược triển khai ứng dụng: Blue/Green Deployment, Canary Release và Rolling Update?",
        "answer_hint": "Rolling Update: Cập nhật từng Pod cũ thành Pod mới theo thứ tự; tiết kiệm tài nguyên nhưng cả hai phiên bản cùng tồn tại trong thời gian chuyển tiếp. Blue/Green: Chạy song song 2 môi trường độc lập (Blue cũ, Green mới), chuyển toàn bộ 100% traffic qua Green khi đã kiểm thử xong; rollback tức thì nhưng tốn gấp đôi tài nguyên. Canary: Chuyển một tỷ lệ nhỏ traffic (5-10%) sang phiên bản mới để kiểm tra metric lỗi trước khi mở rộng dần lên 100%."
    },
    {
        "category_id": 4, "level_id": 4, # Middle
        "question": "Khái niệm Infrastructure as Code (IaC) và cách quản lý trạng thái (State) với Terraform?",
        "answer_hint": "IaC định nghĩa hạ tầng máy chủ, mạng, cơ sở dữ liệu bằng mã nguồn khai báo có thể quản lý qua Git. Terraform lưu trạng thái hạ tầng thực tế trong tệp terraform.tfstate. Trong môi trường nhóm, bắt buộc dùng Remote Backend (S3 + DynamoDB state locking hoặc Terraform Cloud) để tránh xung đột concurrent updates, mã hóa bảo vệ bí mật và lưu giữ lịch sử thay đổi."
    },
    {
        "category_id": 4, "level_id": 5, # Senior
        "question": "Kiến trúc High Availability (HA) và Disaster Recovery (DR) trên Cloud: RTO và RPO?",
        "answer_hint": "RPO (Recovery Point Objective): Lượng dữ liệu tối đa chấp nhận bị mất tính theo thời gian. RTO (Recovery Time Objective): Thời gian tối đa cho phép hệ thống phục hồi hoạt động. Các mô hình DR từ thấp đến cao: Backup & Restore -> Pilot Light -> Warm Standby -> Multi-Region Active-Active. HA đạt được nhờ triển khai Multi-AZ, tự động Auto-Scaling, database read-replicas và failover tự động."
    },
    {
        "category_id": 4, "level_id": 6, # Lead
        "question": "Chiến lược thiết lập văn hóa DevSecOps và tự động hóa bảo mật trong CI/CD pipeline?",
        "answer_hint": "Áp dụng nguyên lý Shift-Left: Bảo mật từ giai đoạn viết mã. Tích hợp trong CI/CD: 1. Pre-commit hooks kiểm tra lộ secrets (Gitleaks, Trufflehog). 2. SAST (Static Application Security Testing) quét lỗ hổng mã nguồn (SonarQube). 3. SCA (Software Composition Analysis) quét lỗ hổng thư viện phụ thuộc (Snyk, Trivy). 4. DAST (Dynamic Testing) quét ứng dụng đang chạy (OWASP ZAP). 5. Ký số image và quản lý chính sách bảo mật qua OPA/Kyverno."
    },

    # Category 5: Mobile App (id=5)
    {
        "category_id": 5, "level_id": 2, # Fresher
        "question": "Vòng đời (Lifecycle) của Activity (Android) hoặc ViewController (iOS) và lưu ý quản lý tài nguyên?",
        "answer_hint": "Android: onCreate -> onStart -> onResume -> onPause -> onStop -> onDestroy. iOS: viewDidLoad -> viewWillAppear -> viewDidAppear -> viewWillDisappear -> viewDidDisappear. Lưu ý: Chỉ khởi tạo tài nguyên nặng một lần trong onCreate/viewDidLoad; hủy đăng ký listeners, timers, camera và giải phóng memory trong onPause/onStop hoặc viewWillDisappear để tránh Memory Leak và hao pin."
    },
    {
        "category_id": 5, "level_id": 3, # Junior
        "question": "So sánh phát triển ứng dụng Native (Kotlin/Swift) và Cross-Platform (Flutter/React Native)?",
        "answer_hint": "Native (Kotlin/Swift): Truy cập trực tiếp toàn bộ API phần cứng, hiệu năng đồ họa tối đa, thích hợp ứng dụng xử lý audio/video thời gian thực hoặc game 3D, nhưng chi phí bảo trì gấp đôi vì 2 codebase. Cross-Platform (Flutter/React Native): Chia sẻ 80-95% mã nguồn giữa iOS và Android, rút ngắn thời gian ra mắt thị trường (Time to Market); Flutter vẽ canvas trực tiếp bằng Skia/Impeller cho hiệu năng mượt, React Native tận dụng hệ sinh thái JavaScript rộng lớn."
    },
    {
        "category_id": 5, "level_id": 3, # Junior
        "question": "Cách thiết kế tính năng lưu trữ Offline-First và đồng bộ dữ liệu trên thiết bị di động?",
        "answer_hint": "Ứng dụng luôn đọc và ghi dữ liệu vào local database (Room trên Android, CoreData/SwiftData trên iOS, WatermelonDB/Isar). Mỗi bản ghi có cờ sync_status ('SYNCED', 'PENDING_INSERT', 'PENDING_UPDATE', 'PENDING_DELETE') và timestamp. Background Sync Worker (WorkManager / BGAppRefreshTask) tự động đẩy các thay đổi lên server khi có mạng và giải quyết xung đột bằng chiến lược Last-Write-Wins hoặc phân xử theo phiên bản."
    },
    {
        "category_id": 5, "level_id": 4, # Middle
        "question": "Tối ưu hóa hiệu năng ứng dụng di động: đạt 60fps/120fps và khắc phục Memory Leak?",
        "answer_hint": "1. Khung hình (Frame Rendering): Giữ thời gian xử lý main thread dưới 16ms (cho 60fps) hoặc 8ms (cho 120fps). Đẩy I/O và tính toán nặng sang background thread (Coroutines/Dispatchers.IO). 2. Danh sách: Tái sử dụng views triệt để (RecyclerView ViewHolder), lazy-loading ảnh có kích thước phù hợp màn hình. 3. Memory Leak: Dùng LeakCanary (Android) hoặc Xcode Instruments để phát hiện retain cycle (Strong reference trong closures/callbacks); luôn dùng weak references khi cần."
    },
    {
        "category_id": 5, "level_id": 4, # Middle
        "question": "Cơ chế Deep Linking và Universal Links: cấu hình và xử lý điều hướng an toàn?",
        "answer_hint": "Custom URL Schemes (myapp://) có nhược điểm dễ bị ứng dụng khác chiếm quyền. Giải pháp chuẩn là Universal Links (iOS) và App Links (Android) sử dụng tên miền HTTPS có xác thực hai chiều: server lưu file xác thực (apple-app-site-association hoặc assetlinks.json), hệ điều hành tự động mở app nếu đã cài, hoặc fallback mở trình duyệt web nếu chưa cài. Luôn validate và sanitize payload trong deep link để phòng chống lỗ hổng bảo mật điều hướng."
    },
    {
        "category_id": 5, "level_id": 5, # Senior
        "question": "Thiết kế kiến trúc Clean Architecture cho ứng dụng di động quy mô lớn?",
        "answer_hint": "Phân chia 3 tầng độc lập: 1. Domain Layer (Pure Kotlin/Swift): Chứa Entities, Value Objects và Use Cases/Interactors, độc lập hoàn toàn với framework và thư viện bên ngoài. 2. Data Layer: Quản lý Repositories, Data Sources (Local DB, Remote API), Model mappers. 3. Presentation Layer: UI Views, ViewModels / State Notifiers (tuân thủ MVI hoặc MVVM). Phụ thuộc luôn hướng vào trong Domain Layer thông qua Dependency Inversion."
    },

    # Category 6: QA & Automation (id=6)
    {
        "category_id": 6, "level_id": 2, # Fresher
        "question": "Phân biệt Functional Testing và Non-Functional Testing, lấy ví dụ cụ thể?",
        "answer_hint": "Functional Testing (Kiểm thử chức năng) xác minh phần mềm hoạt động đúng theo yêu cầu nghiệp vụ mô tả (ví dụ: đăng nhập với đúng email/password thành công, tính toán thuế đúng công thức). Non-Functional Testing (Kiểm thử phi chức năng) đánh giá đặc tính vận hành của hệ thống như hiệu năng (Performance/Load), độ bảo mật (Security), khả năng chịu tải (Stress), tính dễ sử dụng (Usability) và khả năng tương thích trình duyệt/thiết bị."
    },
    {
        "category_id": 6, "level_id": 3, # Junior
        "question": "Trình bày mô hình Test Pyramid và tỷ trọng phân bổ giữa Unit Test, Integration Test và E2E Test?",
        "answer_hint": "Test Pyramid khuyến nghị: Đáy tháp lớn nhất là Unit Tests (70%) chạy cực nhanh, chi phí bảo trì thấp, kiểm tra từng hàm/component độc lập. Tầng giữa là Integration Tests (20%) kiểm tra sự tương tác giữa các module hoặc giữa ứng dụng với database/external APIs. Đỉnh tháp là E2E Tests (10%) mô phỏng hành vi người dùng thật trên trình duyệt/mobile; cho độ tin cậy cao nhất nhưng chạy chậm và dễ bị 'flaky'."
    },
    {
        "category_id": 6, "level_id": 3, # Junior
        "question": "Các kỹ thuật thiết kế test case: Phân vùng tương đương và Phân tích giá trị biên?",
        "answer_hint": "Phân vùng tương đương (Equivalence Partitioning): Chia miền dữ liệu đầu vào thành các nhóm hợp lệ và không hợp lệ; chỉ cần chọn 1 đại diện trong mỗi nhóm để kiểm thử, giúp giảm số lượng test case mà vẫn đảm bảo độ phủ. Phân tích giá trị biên (Boundary Value Analysis): Lỗi thường xuất hiện nhiều nhất ở ranh giới giữa các phân vùng; chọn các giá trị tại biên, ngay dưới biên và ngay trên biên (ví dụ tuổi từ 18-60 -> test 17, 18, 19, 59, 60, 61)."
    },
    {
        "category_id": 6, "level_id": 4, # Middle
        "question": "Xây dựng Automation Test Framework với Playwright/Selenium theo mô hình Page Object Model (POM)?",
        "answer_hint": "Mô hình POM tách biệt giữa logic test và cấu trúc UI: Mỗi trang web hoặc component được đại diện bằng một class riêng chứa các locators và phương thức hành động (ví dụ LoginPage.fillCredentials(), LoginPage.submit()). Các file test spec chỉ gọi các hàm nghiệp vụ của Page Object. Ưu điểm: Khi UI thay đổi giao diện/selectors, chỉ cần cập nhật một nơi duy nhất trong Page Object mà không phải sửa hàng chục test cases."
    },
    {
        "category_id": 6, "level_id": 4, # Middle
        "question": "Chiến lược kiểm thử hiệu năng và chịu tải (Load Testing & Stress Testing) với k6 hoặc JMeter?",
        "answer_hint": "Quy trình: 1. Xác định KPIs mục tiêu: TPS (Transactions Per Second), Response Time (p95, p99 < 500ms), Error Rate (< 0.1%). 2. Load Testing: Tăng tải dần lên mức người dùng dự kiến cao nhất (Peak Load) và duy trì trong thời gian dài (Soak Test) để phát hiện rò rỉ bộ nhớ. 3. Stress Testing: Đẩy tải vượt quá giới hạn thiết kế để xác định điểm gãy (breaking point) và kiểm tra khả năng tự phục hồi của hệ thống (Graceful Degradation)."
    },
    {
        "category_id": 6, "level_id": 5, # Senior
        "question": "Tích hợp Continuous Testing vào CI/CD pipeline và giải pháp khắc phục Flaky Test?",
        "answer_hint": "1. Chạy Unit/Integration test ở mỗi pull request. 2. E2E tests chạy theo ma trận song song (Parallel execution qua Docker containers) để rút ngắn thời gian build dưới 10 phút. 3. Khắc phục Flaky Test: Tuyệt đối không dùng sleep cứng mà dùng explicit wait / auto-waiting của Playwright; cô lập dữ liệu test bằng cách tạo dynamic test tenant/user độc lập; triển khai cơ chế retry tự động tối đa 1 lần kèm gắn tag theo dõi tỉ lệ flaky để refactor kịp thời."
    }
]

def seed():
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE interview_questions"))
        conn.execute(text("TRUNCATE TABLE interview_practice"))
        stmt = text("""
            INSERT INTO interview_questions (category_id, level_id, question, answer_hint, is_published)
            VALUES (:category_id, :level_id, :question, :answer_hint, 1)
        """)
        for q in QUESTIONS:
            conn.execute(stmt, q)
        conn.commit()
        cnt = conn.execute(text("SELECT COUNT(*) FROM interview_questions")).scalar()
        print(f"Seed completed! Total questions in database: {cnt}")

if __name__ == "__main__":
    seed()
