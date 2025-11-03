import asyncio
import os
import unittest
from unittest.mock import MagicMock

from pydantic import BaseModel, Field

from .converse import Converse, Message, ConverseResponse, BaseCallbackHandler

_response = {'ResponseMetadata': {
    'HTTPHeaders': {'connection': 'keep-alive', 'content-length': '1561', 'content-type': 'application/json',
                    'date': 'Sat, 10 May 2025 05:44:20 GMT',
                    'x-amzn-requestid': '1f5910c6-808a-416a-b1a0-ce854b8515b5'}, 'HTTPStatusCode': 200,
    'RequestId': '1f5910c6-808a-416a-b1a0-ce854b8515b5', 'RetryAttempts': 0}, 'metrics': {'latencyMs': 8489},
    'output': {'message': {'content': [{'text': """The image shows a landing pa"""}], 'role': 'assistant'}},
    'stopReason': 'end_turn',
    'usage': {'cacheReadInputTokens': 0, 'cacheWriteInputTokens': 1520, 'inputTokens': 9, 'outputTokens': 278,
              'totalTokens': 1807}}

_structured_response = {'ResponseMetadata': {
    'HTTPHeaders': {'connection': 'keep-alive', 'content-length': '313', 'content-type': 'application/json',
                    'date': 'Sat, 10 May 2025 07:47:58 GMT',
                    'x-amzn-requestid': '5a876a50-839c-450d-b8bb-d8950246d9ef'}, 'HTTPStatusCode': 200,
    'RequestId': '5a876a50-839c-450d-b8bb-d8950246d9ef', 'RetryAttempts': 0}, 'metrics': {'latencyMs': 561}, 'output': {
    'message': {
        'content': [{'toolUse': {'input': {'test_field': 'I am well how are you?'}, 'name': 'TestOutput',
                                 'toolUseId': 'tooluse_2Xiq4x5CSjyIykI2WVuMDA'}}],
        'role': 'assistant'}}, 'stopReason': 'tool_use',
    'usage': {'inputTokens': 452, 'outputTokens': 43, 'totalTokens': 495}}


class TestOutput(BaseModel):
    test_field: str = Field(description='test field, fill with random values', default=None)



class TestConverseRequest(unittest.TestCase):
    def setup_prompt(self):
        prompt = Message()
        prompt.add_text('My text')
        test_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(test_dir, 'fixtures', 'image.png')
        with open(image_path, 'rb') as f:
            prompt.add_image(f.read(), 'png')
        prompt.add_cache_point()
        prompt.add_text('My Changing text')
        return prompt

    def setup_converse(self):
        converse = Converse(model_id="test", region_name='test')
        self.override_response(converse, _response)
        return converse

    def override_response(self, converse, res):
        converse.client.converse = lambda *args, **kwargs: res

    def test_converse(self):
        converse = self.setup_converse()
        response = converse.converse(self.setup_prompt())
        self.assertEqual(len(converse.messages), 2)
        self.assertEqual(response.output.message, converse.messages[-1])

    def test_no_context_invoke(self):
        converse = self.setup_converse()
        response = converse.invoke(self.setup_prompt())
        self.assertEqual(len(converse.messages), 0)
        self.assertEqual(response, ConverseResponse.from_dict(_response))

    def test_context_invoke(self):
        converse = self.setup_converse()
        converse.converse(self.setup_prompt())
        response = converse.invoke(self.setup_prompt())
        self.assertEqual(len(converse.messages), 2)
        self.assertEqual(response, ConverseResponse.from_dict(_response))

    def test_basic_invoke(self):
        converse = self.setup_converse()
        response = converse.invoke('this is a test prompt')
        self.assertEqual(len(converse.messages), 0)
        self.assertEqual(response, ConverseResponse.from_dict(_response))

    def test_with_structured_output(self):
        converse = Converse(model_id="test")
        structured_converse = converse.with_structured_output(TestOutput)
        self.override_response(structured_converse, _structured_response)
        response = structured_converse.invoke('How are you?')
        self.assertTrue(isinstance(response, TestOutput))

    def test_callbacks(self):
        on_start = MagicMock()
        on_end = MagicMock()

        class Callback(BaseCallbackHandler):
            def on_converse_start(self, converse):
                on_start(converse)

            def on_converse_end(self, response):
                on_end(response)

        converse = self.setup_converse()
        converse.add_callback(Callback())
        converse.converse(self.setup_prompt())
        on_start.assert_called_once_with(converse)
        on_end.assert_called_once_with(ConverseResponse.from_dict(_response))

    def test_content(self):
        converse = self.setup_converse()
        response = converse.invoke('this is a test prompt')
        self.assertEqual(response.content, 'The image shows a landing pa')


class TestAsyncConverseRequest(unittest.TestCase):
    def setup_prompt(self):
        prompt = Message()
        prompt.add_text('My text')
        # Get the directory of the current test file
        test_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(test_dir, 'fixtures', 'image.png')
        with open(image_path, 'rb') as f:
            prompt.add_image(f.read(), 'png')
        prompt.add_cache_point()
        prompt.add_text('My Changing text')
        return prompt

    def setup_async_converse(self):
        converse = Converse(model_id="test", region_name='test')
        self.override_async_response(converse, _response)
        return converse

    def override_async_response(self, converse, res):
        # Mock the client's converse method to return our test response
        converse.client.converse = lambda *args, **kwargs: res

    async def test_ainvoke(self):
        converse = self.setup_async_converse()
        response = await converse.ainvoke(self.setup_prompt())
        self.assertEqual(len(converse.messages), 0)
        self.assertEqual(response, ConverseResponse.from_dict(_response))

    async def test_aconverse(self):
        converse = self.setup_async_converse()
        response = await converse.aconverse(self.setup_prompt())
        self.assertEqual(len(converse.messages), 2)
        self.assertEqual(response.output.message, converse.messages[-1])

    async def test_ainvoke_with_string(self):
        converse = self.setup_async_converse()
        response = await converse.ainvoke('this is a test prompt')
        self.assertEqual(len(converse.messages), 0)
        self.assertEqual(response, ConverseResponse.from_dict(_response))

    async def test_aconverse_with_string(self):
        converse = self.setup_async_converse()
        response = await converse.aconverse('this is a test prompt')
        self.assertEqual(len(converse.messages), 2)
        self.assertEqual(response.output.message, converse.messages[-1])

    async def test_async_with_structured_output(self):
        converse = Converse(model_id="test", region_name='test')
        structured_converse = converse.with_structured_output(TestOutput)
        self.override_async_response(structured_converse, _structured_response)
        response = await structured_converse.ainvoke('How are you?')
        self.assertTrue(isinstance(response, TestOutput))

    async def test_async_callbacks(self):
        on_start = MagicMock()
        on_end = MagicMock()

        class Callback(BaseCallbackHandler):
            def on_converse_start(self, converse):
                on_start(converse)

            def on_converse_end(self, response):
                on_end(response)

        converse = self.setup_async_converse()
        converse.add_callback(Callback())
        await converse.aconverse(self.setup_prompt())
        on_start.assert_called_once_with(converse)
        on_end.assert_called_once_with(ConverseResponse.from_dict(_response))

    async def test_async_content(self):
        converse = self.setup_async_converse()
        response = await converse.ainvoke('this is a test prompt')
        self.assertEqual(response.content, 'The image shows a landing pa')

    # Test runner helper methods for async tests
    def test_ainvoke_sync(self):
        asyncio.run(self.test_ainvoke())

    def test_aconverse_sync(self):
        asyncio.run(self.test_aconverse())

    def test_ainvoke_with_string_sync(self):
        asyncio.run(self.test_ainvoke_with_string())

    def test_aconverse_with_string_sync(self):
        asyncio.run(self.test_aconverse_with_string())

    def test_async_with_structured_output_sync(self):
        asyncio.run(self.test_async_with_structured_output())

    def test_async_callbacks_sync(self):
        asyncio.run(self.test_async_callbacks())

    def test_async_content_sync(self):
        asyncio.run(self.test_async_content())


if __name__ == '__main__':
    unittest.main()
