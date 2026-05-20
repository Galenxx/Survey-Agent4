"""End-to-end integration tests"""
import pytest
import os
import json
from unittest.mock import patch, MagicMock


class TestTaskStorage:
    """测试任务隔离存储"""

    def test_task_storage_creation(self, task_storage):
        """测试任务存储创建"""
        assert task_storage is not None
        assert task_storage.task_id is not None
        assert "test_task" in task_storage.task_id

    def test_task_storage_directories(self, task_storage):
        """测试任务目录创建"""
        assert os.path.exists(task_storage.logs_dir)
        assert os.path.exists(task_storage.papers_dir)
        assert os.path.exists(task_storage.data_dir)

    def test_task_storage_log(self, task_storage):
        """测试日志写入"""
        task_storage.log("test_agent", "Test log message")
        log_path = os.path.join(task_storage.logs_dir, "test_agent.log")
        assert os.path.exists(log_path)
        with open(log_path, "r") as f:
            content = f.read()
            assert "Test log message" in content

    def test_task_storage_save_data(self, task_storage):
        """测试数据保存"""
        data = {"key": "value", "number": 42}
        path = task_storage.save_data("test.json", data)
        assert path.endswith("test.json")
        assert os.path.exists(path)
        with open(path, "r") as f:
            loaded = json.load(f)
            assert loaded["key"] == "value"

    def test_task_storage_complete(self, task_storage):
        """测试任务完成标记"""
        task_storage.complete("Test completed")
        manifest_path = os.path.join(task_storage.task_dir, "task_manifest.json")
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
            assert manifest["status"] == "completed"
            assert manifest["summary"] == "Test completed"

    def test_task_storage_fail(self, task_storage):
        """测试任务失败标记"""
        task_storage.fail("Test error")
        manifest_path = os.path.join(task_storage.task_dir, "task_manifest.json")
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
            assert manifest["status"] == "failed"
            assert manifest["error"] == "Test error"


class TestReportWriter:
    """测试报告写入"""

    def test_report_writer_new_file(self, temp_output_dir):
        """测试新建报告文件"""
        from src.tools.write_report import ReportWriterTool

        tool = ReportWriterTool()
        output_path = os.path.join(temp_output_dir, "report.md")
        result = tool._run(
            content="# Test Report\n\nTest content",
            output_path=output_path,
            append=False
        )

        assert os.path.exists(output_path)
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "Test Report" in content

    def test_report_writer_append(self, temp_output_dir):
        """测试追加报告"""
        from src.tools.write_report import ReportWriterTool

        tool = ReportWriterTool()
        output_path = os.path.join(temp_output_dir, "report.md")

        tool._run(content="# First Section", output_path=output_path, append=False)
        tool._run(content="# Second Section", output_path=output_path, append=True)

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "First Section" in content
            assert "Second Section" in content
