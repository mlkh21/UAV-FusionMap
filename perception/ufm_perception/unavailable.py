"""生成不可用占据观测，不把缺失输入解释为自由空间。"""
import copy


def unavailable_infer(bundle, reason, source_type="derived", resolution=(0.5, 0.5, 0.5),
                      shape=(64, 32, 16), origin=(-16.0, -8.0, -4.0)):
    """保留观测身份和上下文，输出零体素的 unavailable 结果。"""
    source = bundle["header"]
    context = copy.deepcopy(bundle["context"])
    context["source_frame_id"] = "odom"
    context["mapping_frame_id"] = "odom"
    context["reference_timestamp"] = source["timestamp"]
    context["clock_id"] = source["clock_id"]
    context["T_mapping_source"] = [1.0 if row == col else 0.0
                                    for row in range(4) for col in range(4)]
    return dict(
        header=dict(schema_version="0.1", timestamp=source["timestamp"],
                    clock_id=source["clock_id"], run_id=source["run_id"],
                    sample_id="perception.occupancy:" + source["sample_id"],
                    frame_id="odom", source_type=source_type,
                    status="unavailable", reason=str(reason)),
        voxels=[], resolution=list(resolution), shape=list(shape), origin=list(origin),
        context=context, observed_domain_source="unavailable_no_observation",
    )
