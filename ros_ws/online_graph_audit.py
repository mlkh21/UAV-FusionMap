"""运行时在线ROS图的训练监督隔离校验。

该模块只消费 ``rosmaster.getSystemState`` 的结构化结果，不订阅或发布任何话题。
"""


EXPECTED_ONLINE_NODES = (
    '/perf01a_async_runner',
    '/perf01a_source',
    '/perf01a_radar',
    '/perf01a_infrared',
    '/perf01a_sensor',
    '/perf01a_perception',
    '/perf01a_mapping',
)


def _normalize(entries):
    """将XML-RPC的(topic, nodes)数组转为稳定、可序列化的记录。"""
    return [
        dict(topic=str(topic), nodes=sorted(str(node) for node in nodes))
        for topic, nodes in entries
    ]


def validate_online_graph(publishers, subscribers, expected_nodes=EXPECTED_ONLINE_NODES):
    """拒绝不完整或带训练/LiDAR节点的在线图。

    只要图为空、在线链路节点不齐，或任一训练/LiDAR相关话题存在发布者/订阅者，
    结果就不能通过。``expected_nodes``用于避免空图的反例被误判为隔离成功。
    """
    normalized_publishers = _normalize(publishers)
    normalized_subscribers = _normalize(subscribers)
    all_nodes = {
        node
        for entry in normalized_publishers + normalized_subscribers
        for node in entry['nodes']
    }
    errors = []
    missing_nodes = sorted(set(expected_nodes) - all_nodes)
    if not all_nodes:
        errors.append('online graph is empty')
    if missing_nodes:
        errors.append('online graph missing expected nodes: ' + ', '.join(missing_nodes))

    forbidden_topic_markers = ('training', 'lidar')
    forbidden_topics = sorted({
        entry['topic']
        for entry in normalized_publishers + normalized_subscribers
        if any(marker in entry['topic'].lower() for marker in forbidden_topic_markers)
    })
    if forbidden_topics:
        errors.append('online graph contains training or LiDAR topics: ' + ', '.join(forbidden_topics))

    forbidden_nodes = sorted({
        node
        for node in all_nodes
        if 'training' in node.lower() or 'lidar' in node.lower()
    })
    if forbidden_nodes:
        errors.append('online graph contains training or LiDAR nodes: ' + ', '.join(forbidden_nodes))

    return dict(
        passed=not errors,
        errors=errors,
        missing_nodes=missing_nodes,
        forbidden_topics=forbidden_topics,
        forbidden_nodes=forbidden_nodes,
        publishers=normalized_publishers,
        subscribers=normalized_subscribers,
    )
