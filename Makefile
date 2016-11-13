all: protobuf

protobuf:
	python -m grpc.tools.protoc -I defs --python_out=protobounce/proto --grpc_python_out=protobounce/proto defs/*.proto
