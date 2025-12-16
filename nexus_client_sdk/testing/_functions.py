"""Support functions for writing tests for Nexus apps"""
import base64
import gzip
import uuid

from adapta.storage.blob.base import StorageClient
from adapta.storage.models import DataPath
from adapta.storage.models.formatters import DictJsonSerializationFormat

from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload, CompressedPayload


#  Copyright (c) 2023-2026. ECCO Data & AI and other project contributors.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#


def generate_payload_url(
    base_path: DataPath, payload_object: AlgorithmPayload, storage_client: StorageClient, compress_payload: bool = False
) -> tuple[str, str]:
    """
    Uploads provided data to the path and returns a signed URL for the uploaded object, as well as its request_id
    In addition, it was added to support optional compression of the payload.

    :param base_path:
    :param payload_object:
    :param storage_client:
    :param compress_payload: if True, the payload will be compressed using gzip before uploading
    :return:
    """
    data = DictJsonSerializationFormat().deserialize(payload_object.to_json().encode(encoding="utf-8"))
    obj_name = str(uuid.uuid4())
    if compress_payload:
        serialized_data = DictJsonSerializationFormat().serialize(data)
        compressed_content = gzip.compress(serialized_data)
        encoded_compressed_content = base64.b64encode(compressed_content)
        data = {
            CompressedPayload.CONTENT: encoded_compressed_content.decode("utf-8"),
            CompressedPayload.DECOMPRESSION_IMPORT_PATH: "gzip.decompress",
        }
    upload_path = base_path.__class__.from_hdfs_path("/".join([base_path.to_hdfs_path(), obj_name]))
    storage_client.save_data_as_blob(
        data=data, blob_path=upload_path, serialization_format=DictJsonSerializationFormat, overwrite=True
    )
    return storage_client.get_blob_uri(upload_path), obj_name
