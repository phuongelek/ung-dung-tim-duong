# Tìm đường bằng thuật toán A* trên bản đồ TP.HCM

Bài tập nhóm môn **Nhập môn Trí tuệ nhân tạo**, Học viện Công nghệ Bưu chính Viễn thông (PTIT).

Ứng dụng tìm đường ngắn nhất giữa hai điểm trên bản đồ đường phố thật của TP.HCM bằng thuật toán
**A\*** (tìm kiếm có thông tin trong không gian trạng thái). Dữ liệu đường phố lấy từ
[OpenStreetMap](https://www.openstreetmap.org); giao diện viết bằng Python + Pygame.

## Tính năng

- Click chọn điểm đầu và điểm đích trên bản đồ, xem A* "loang" từng bước dọc theo các con đường thật.
- Hiện tên đường trên bản đồ (phóng to càng nhiều tên); tên các đường trên lộ trình được làm nổi bật.
- Hiển thị kết quả: quãng đường, khoảng cách chim bay, số nút đã mở rộng, kích thước OPEN lớn nhất,
  thời gian tính và lộ trình theo tên đường.
- Tôn trọng đường một chiều.
- Nút **Mở trên Google Maps** để đối chiếu với lộ trình Google gợi ý.
- Chọn điểm mới sau khi đã có kết quả thì đường đi được tính lại ngay.

## Thuật toán

Bài toán được mô hình hóa thành tìm kiếm trên không gian trạng thái:

| Thành phần | Trong bài toán |
|---|---|
| Trạng thái | Một giao lộ (đỉnh của đồ thị có hướng) |
| Trạng thái đầu / đích | Giao lộ gần điểm người dùng click nhất |
| Hành động | Đi theo một đoạn đường sang giao lộ kề |
| Chi phí | Độ dài đoạn đường (mét) |
| Heuristic h(n) | Khoảng cách chim bay từ n đến đích (công thức Haversine) |

A* chọn nút có `f(n) = g(n) + h(n)` nhỏ nhất để mở rộng, trong đó `g(n)` là quãng đường đã đi từ điểm đầu.
Khoảng cách chim bay không bao giờ lớn hơn quãng đường đi thật, nên heuristic là **chấp nhận được**
và A* luôn trả về đường đi **ngắn nhất**.

## Cài đặt

Yêu cầu Python 3.10 trở lên.

```bash
git clone <địa chỉ repo này>
cd <tên thư mục repo>
pip install -r requirements.txt
```

## Chạy chương trình

**Bước 1: chuẩn bị dữ liệu bản đồ** (bỏ qua nếu thư mục `data/` đã có file `hcm_map.json`)

```bash
python prepare_map.py
```

Lệnh này tải mạng lưới đường bán kính 3 km quanh chợ Bến Thành từ OpenStreetMap (cần Internet,
chỉ chạy một lần). Nếu báo lỗi `502 Bad Gateway` / "server is currently at capacity" thì máy chủ
Overpass của OpenStreetMap đang quá tải: đợi vài phút rồi chạy lại.

Muốn đổi vùng bản đồ:

```bash
python prepare_map.py --lat 10.7546 --lon 106.6631 --dist 2500
```

`--lat`, `--lon` là tọa độ tâm (click chuột phải trên Google Maps để lấy), `--dist` là bán kính
tính bằng mét, nên để 2000 – 4000.

**Bước 2: mở ứng dụng**

```bash
python main.py
```

## Hướng dẫn sử dụng

| Thao tác | Phím / chuột |
|---|---|
| Chọn điểm đầu, rồi điểm đích | Click chuột trái |
| Chọn điểm đích | Click chuột phải |
| Di chuyển bản đồ | Kéo chuột trái |
| Phóng to / thu nhỏ | Cuộn chuột |
| Chạy A* | `Space` |
| Xóa kết quả / bỏ chọn điểm | `C` / `N` |
| Vừa khung / đảo chiều đi | `F` / `V` |
| Mở trên Google Maps | `G` |
| Ẩn / hiện tên đường | `L` |
| Tốc độ mô phỏng | `+` / `-` |
| Thoát | `Esc` |

## Cấu trúc thư mục

```
├── core/
│   ├── astar.py        Thuật toán A* (OPEN = hàng đợi ưu tiên, CLOSED = tập đã xét)
│   ├── problems.py     Mô hình bài toán trên bản đồ, heuristic Haversine
│   └── baselines.py    BFS, DFS, UCS, Greedy (chỉ dùng để so sánh)
├── ui/
│   ├── common.py       Màu sắc, phông chữ, nút bấm
│   └── map_view.py     Giao diện bản đồ: vẽ đường, tên đường, mô phỏng A*
├── data/               Dữ liệu bản đồ (hcm_map.json)
├── main.py             Chạy ứng dụng
├── prepare_map.py      Tải dữ liệu OpenStreetMap -> data/hcm_map.json
├── compare.py          So sánh A* với các thuật toán khác
└── requirements.txt    Danh sách thư viện cần cài
```

## So sánh với các thuật toán khác

```bash
python compare.py --trials 50
```

Chạy BFS, DFS, UCS, Greedy và A* trên cùng các cặp điểm ngẫu nhiên, chia theo khoảng cách
(gần, trung bình, xa). Kết quả gồm số lần tìm được đường tối ưu, số nút mở rộng trung bình và
thời gian trung bình, được in ra màn hình và lưu vào `results/compare_results.csv`.

## Ghi chú

- A* trong ứng dụng tối ưu theo **quãng đường**, còn Google Maps tối ưu theo **thời gian** (có tính
  kẹt xe, tốc độ từng loại đường...), nên hai lộ trình có thể khác nhau.
- Khi tạo dữ liệu, chỉ giữ thành phần liên thông mạnh lớn nhất của đồ thị để mọi cặp điểm đều có
  đường đi; độ dài mỗi đoạn đường được đảm bảo không nhỏ hơn khoảng cách chim bay giữa hai đầu mút.
- Vùng bản đồ chọn theo **tâm + bán kính** thay vì tên quận, vì sau đợt sắp xếp đơn vị hành chính
  năm 2025 cấp quận đã bỏ, truy vấn theo tên quận có thể không còn khớp.

## Nguồn dữ liệu

Dữ liệu bản đồ © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
phát hành theo giấy phép Open Database License (ODbL).
