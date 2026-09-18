# DATA_FORMAT v0.1：timestamp为非负采样纳秒，不是ROS接收时间。
uint8 SIMULATION=0
uint8 MEASURED=1
uint8 FIXTURE=2
uint8 MODEL=3
uint8 DERIVED=4
uint8 VALID=0
uint8 DEGRADED=1
uint8 UNAVAILABLE=2
string schema_version
int64 timestamp
string clock_id
string run_id
string sample_id
string frame_id
uint8 source_type
uint8 status
string reason
