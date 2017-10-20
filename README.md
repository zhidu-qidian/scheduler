# 爬虫任务调度服务


定时将指定value放入指定类型的redis key里，并用MONGODB做持久化



## /tasks  form

### POST 创建一个定时任务,相同的id,直接更新已有的任务

```json
{
  "id": "wdjklit43jijkdjanbvah",
  "rule": "T30S",
  "struct": "list",
  "key": "schedule:spiders:news:common",
  "value": "value"
}
```

### DELETE 删除指定的任务

```json
{
  "id": "wdjklit43jijkdjanbvah"
}
```

### 字段说明

- id string 任务的唯一标识,相同的 id 认为是同一任务
- rule string 调度格式
- struct string key 的数据结构,只支持 list,set
- key string redis 的 key
- value string 要放入 key 中的值

#### rule 格式说明

支持 cron,interval 两种定时重复任务, date 一种一次性任务

##### cron 格式

month;day;hour;minute;second

分号分隔各个字段

##### interval 格式

T1D2H13M30S

- T 开头
- D 天
- H 小时
- M 分钟
- S 秒

列如: T2D30S 表示间隔2天30秒

##### date 格式

"0000-00-00 00:00:00"

列如: "2017-03-09 18:18:30" 表示在 2017年3月9号18时18分30秒
