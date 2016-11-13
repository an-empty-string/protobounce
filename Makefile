all: protobuf

protobuf:
	python -m grpc.tools.protoc -I proto --python_out=protobounce/proto --grpc_python_out=protobounce/proto proto/*.proto
