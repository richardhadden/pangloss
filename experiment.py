a = {
    "carried_out": [
        {
            "_type": "Event:BaseNode:HeadNode",
            "_id": 15,
            "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:15",
            "label": "3An Event",
            "uuid": "066fe86c-ad4c-7f9e-8000-061cbdc5b7b1",
            "type": "Event",
            "carried_out_by": [
                {
                    "_head_uuid": "066fe86c-ad4c-7f9e-8000-061cbdc5b7b1",
                    "carried_out_by.reverse_name": "carried_out",
                    "label": "3 Smith acts as proxy for jones",
                    "type": "WithProxyActor[Identification[test_create_with_reified_node.<locals>.Person]]",
                    "_type": "ReifiedRelation:WithProxyActor:ReifiedRelationNode",
                    "carried_out_by.relation_labels": ["carried_out_by"],
                    "_id": 17,
                    "carried_out_by._id": 24,
                    "proxy": [
                        {
                            "proxy._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:23",
                            "_type": "Identification:ReifiedRelation",
                            "_head_uuid": "066fe86c-ad4c-7f9e-8000-061cbdc5b7b1",
                            "proxy.reverse_relation_labels": ["acts_as_proxy_in"],
                            "_id": 19,
                            "target": [
                                {
                                    "_type": "Person:BaseNode:HeadNode",
                                    "target._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:22",
                                    "target.certainty": 1,
                                    "_id": 1,
                                    "target.relation_labels": ["target"],
                                    "target.reverse_name": "is_target_of",
                                    "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:1",
                                    "label": "JohnSmith",
                                    "uuid": "066fe86c-8acd-7d2f-8000-fe0a941df986",
                                    "target.reverse_relation_labels": ["is_target_of"],
                                    "type": "Person",
                                    "target._id": 22,
                                }
                            ],
                            "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:19",
                            "uuid": "066fe86c-ad4e-73ef-8000-9e817123fdd6",
                            "proxy.reverse_name": "acts_as_proxy_in",
                            "type": "Identification[test_create_with_reified_node.<locals>.Person]",
                            "proxy._id": 23,
                            "proxy.relation_labels": ["proxy"],
                        }
                    ],
                    "target": [
                        {
                            "_type": "Identification:ReifiedRelation",
                            "_head_uuid": "066fe86c-ad4c-7f9e-8000-061cbdc5b7b1",
                            "target._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:21",
                            "_id": 18,
                            "target.relation_labels": ["target"],
                            "target": [
                                {
                                    "_type": "Person:BaseNode:HeadNode",
                                    "target._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:20",
                                    "target.certainty": 1,
                                    "_id": 3,
                                    "target.relation_labels": ["target"],
                                    "target.reverse_name": "is_target_of",
                                    "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:3",
                                    "label": "TobyJones",
                                    "uuid": "066fe86c-8d83-72db-8000-6162ab69e5f2",
                                    "target.reverse_relation_labels": ["is_target_of"],
                                    "type": "Person",
                                    "target._id": 20,
                                }
                            ],
                            "target.reverse_name": "is_target_of",
                            "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:18",
                            "uuid": "066fe86c-ad4d-7c11-8000-fdfd875af2f0",
                            "target.reverse_relation_labels": ["is_target_of"],
                            "type": "Identification[test_create_with_reified_node.<locals>.Person]",
                            "target._id": 21,
                        }
                    ],
                    "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:17",
                    "carried_out_by.reverse_relation_labels": ["carried_out"],
                    "carried_out_by._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:24",
                    "uuid": "066fe86c-ad4d-76d3-8000-c5d7307ceb73",
                }
            ],
            "bind": "carried_out",
        }
    ],
    "acts_as_proxy_in": [
        {
            "_type": "Event:BaseNode:HeadNode",
            "_id": 10,
            "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:10",
            "label": "2An Event",
            "uuid": "066fe86c-a9d3-7ad5-8000-3c3e6d2714cd",
            "type": "Event",
            "carried_out_by": [
                {
                    "_head_uuid": "066fe86c-a9d3-7ad5-8000-3c3e6d2714cd",
                    "carried_out_by.reverse_name": "carried_out",
                    "label": "2 Jones acts as proxy for Smith",
                    "type": "WithProxyActor[Identification[test_create_with_reified_node.<locals>.Person]]",
                    "_type": "ReifiedRelation:WithProxyActor:ReifiedRelationNode",
                    "carried_out_by.relation_labels": ["carried_out_by"],
                    "_id": 12,
                    "carried_out_by._id": 17,
                    "proxy": [
                        {
                            "proxy._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:16",
                            "_type": "Identification:ReifiedRelation",
                            "_head_uuid": "066fe86c-a9d3-7ad5-8000-3c3e6d2714cd",
                            "proxy.reverse_relation_labels": ["acts_as_proxy_in"],
                            "_id": 14,
                            "target": [
                                {
                                    "_type": "Person:BaseNode:HeadNode",
                                    "target._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:15",
                                    "target.certainty": 1,
                                    "_id": 3,
                                    "target.relation_labels": ["target"],
                                    "target.reverse_name": "is_target_of",
                                    "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:3",
                                    "label": "TobyJones",
                                    "uuid": "066fe86c-8d83-72db-8000-6162ab69e5f2",
                                    "target.reverse_relation_labels": ["is_target_of"],
                                    "type": "Person",
                                    "target._id": 15,
                                }
                            ],
                            "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:14",
                            "uuid": "066fe86c-a9d5-70ca-8000-2af02b6cfc3a",
                            "proxy.reverse_name": "acts_as_proxy_in",
                            "type": "Identification[test_create_with_reified_node.<locals>.Person]",
                            "proxy._id": 16,
                            "proxy.relation_labels": ["proxy"],
                        }
                    ],
                    "target": [
                        {
                            "_type": "Identification:ReifiedRelation",
                            "_head_uuid": "066fe86c-a9d3-7ad5-8000-3c3e6d2714cd",
                            "target._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:14",
                            "_id": 13,
                            "target.relation_labels": ["target"],
                            "target": [
                                {
                                    "_type": "Person:BaseNode:HeadNode",
                                    "target._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:13",
                                    "target.certainty": 1,
                                    "_id": 1,
                                    "target.relation_labels": ["target"],
                                    "target.reverse_name": "is_target_of",
                                    "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:1",
                                    "label": "JohnSmith",
                                    "uuid": "066fe86c-8acd-7d2f-8000-fe0a941df986",
                                    "target.reverse_relation_labels": ["is_target_of"],
                                    "type": "Person",
                                    "target._id": 13,
                                }
                            ],
                            "target.reverse_name": "is_target_of",
                            "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:13",
                            "uuid": "066fe86c-a9d4-7801-8000-72349b2a76ca",
                            "target.reverse_relation_labels": ["is_target_of"],
                            "type": "Identification[test_create_with_reified_node.<locals>.Person]",
                            "target._id": 14,
                        }
                    ],
                    "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:12",
                    "carried_out_by.reverse_relation_labels": ["carried_out"],
                    "carried_out_by._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:17",
                    "uuid": "066fe86c-a9d4-72b3-8000-dc45df6d4f7a",
                }
            ],
            "bind": "acts_as_proxy_in",
        },
        {
            "_type": "Event:BaseNode:HeadNode",
            "_id": 5,
            "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:5",
            "label": "An Event",
            "uuid": "066fe86c-8f3c-79ff-8000-344748d9ca60",
            "type": "Event",
            "carried_out_by": [
                {
                    "_head_uuid": "066fe86c-8f3c-79ff-8000-344748d9ca60",
                    "carried_out_by.reverse_name": "carried_out",
                    "label": "Jones acts as proxy for Smith",
                    "type": "WithProxyActor[Identification[test_create_with_reified_node.<locals>.Person]]",
                    "_type": "ReifiedRelation:WithProxyActor:ReifiedRelationNode",
                    "carried_out_by.relation_labels": ["carried_out_by"],
                    "_id": 7,
                    "carried_out_by._id": 10,
                    "proxy": [
                        {
                            "proxy._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:9",
                            "_type": "Identification:ReifiedRelation",
                            "_head_uuid": "066fe86c-8f3c-79ff-8000-344748d9ca60",
                            "proxy.reverse_relation_labels": ["acts_as_proxy_in"],
                            "_id": 9,
                            "target": [
                                {
                                    "_type": "Person:BaseNode:HeadNode",
                                    "target._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:8",
                                    "target.certainty": 1,
                                    "_id": 3,
                                    "target.relation_labels": ["target"],
                                    "target.reverse_name": "is_target_of",
                                    "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:3",
                                    "label": "TobyJones",
                                    "uuid": "066fe86c-8d83-72db-8000-6162ab69e5f2",
                                    "target.reverse_relation_labels": ["is_target_of"],
                                    "type": "Person",
                                    "target._id": 8,
                                }
                            ],
                            "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:9",
                            "uuid": "066fe86c-8f3e-71a8-8000-b65e7df49e8c",
                            "proxy.reverse_name": "acts_as_proxy_in",
                            "type": "Identification[test_create_with_reified_node.<locals>.Person]",
                            "proxy._id": 9,
                            "proxy.relation_labels": ["proxy"],
                        }
                    ],
                    "target": [
                        {
                            "_type": "Identification:ReifiedRelation",
                            "_head_uuid": "066fe86c-8f3c-79ff-8000-344748d9ca60",
                            "target._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:7",
                            "_id": 8,
                            "target.relation_labels": ["target"],
                            "target": [
                                {
                                    "_type": "Person:BaseNode:HeadNode",
                                    "target._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:6",
                                    "target.certainty": 1,
                                    "_id": 1,
                                    "target.relation_labels": ["target"],
                                    "target.reverse_name": "is_target_of",
                                    "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:1",
                                    "label": "JohnSmith",
                                    "uuid": "066fe86c-8acd-7d2f-8000-fe0a941df986",
                                    "target.reverse_relation_labels": ["is_target_of"],
                                    "type": "Person",
                                    "target._id": 6,
                                }
                            ],
                            "target.reverse_name": "is_target_of",
                            "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:8",
                            "uuid": "066fe86c-8f3d-776e-8000-e319b885b7b8",
                            "target.reverse_relation_labels": ["is_target_of"],
                            "type": "Identification[test_create_with_reified_node.<locals>.Person]",
                            "target._id": 7,
                        }
                    ],
                    "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:7",
                    "carried_out_by.reverse_relation_labels": ["carried_out"],
                    "carried_out_by._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:10",
                    "uuid": "066fe86c-8f3d-71ed-8000-83de92641f08",
                }
            ],
            "bind": "acts_as_proxy_in",
        },
    ],
}

print(len(a["carried_out"]))

for i in a["carried_out"]:
    print(i["label"])


print(len(a["acts_as_proxy_in"]))

for i in a["acts_as_proxy_in"]:
    print(i["label"])
