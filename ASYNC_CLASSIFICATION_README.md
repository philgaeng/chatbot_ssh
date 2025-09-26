# Async Classification for Nepal Chatbot

This document explains the new asynchronous classification functionality that uses Celery to process grievance classification and summarization without blocking the chatbot conversation.

## Overview

The async classification system provides several advantages:

1. **Non-blocking**: The chatbot doesn't wait for LLM processing to continue the conversation
2. **Automatic retries**: Celery handles retries and failures natively
3. **Better user experience**: Users can continue with the conversation while classification happens in the background
4. **Scalability**: Multiple classifications can run in parallel

## Architecture

### Components

1. **`ActionTriggerAsyncClassification`**: Launches the async classification task
2. **`ActionCheckClassificationStatus`**: Checks the status of running classification tasks
3. **`classify_and_summarize_grievance_task`**: Celery task that performs the actual classification
4. **Modified form validation**: Updated to handle async classification status

### Flow

1. User completes grievance details form
2. `ActionTriggerAsyncClassification` launches Celery task
3. User proceeds to grievance summary form
4. Form validation checks classification status
5. If complete, shows results; if still processing, shows progress message
6. User can continue with the conversation while classification runs

## New Slots

- `classification_task_id`: Stores the Celery task ID for tracking
- `classification_status`: Tracks the status ('processing', 'completed', 'failed', 'skipped')

## New Actions

### ActionTriggerAsyncClassification

Launches the async classification task when the grievance details form is completed.

**Location**: `actions/form_grievance.py`

**Usage**: Automatically called after grievance details form completion

### ActionCheckClassificationStatus

Checks the status of a running classification task and updates slots accordingly.

**Location**: `actions/form_grievance.py`

**Usage**: Can be called manually or automatically by form validation

## Modified Components

### ActionAskGrievanceSummaryFormGrievanceListCatConfirmed

Updated to check for async classification status and handle the results.

**Location**: `actions/form_validation_grievance_categories.py`

**Changes**:
- Checks if classification is still processing
- Polls Celery task status
- Updates slots with classification results
- Handles failures gracefully

## Configuration

### Celery Configuration

The async classification uses the existing Celery configuration:

- **Broker**: Redis with password authentication
- **Queue**: `llm_queue` for LLM processing tasks
- **Concurrency**: 6 workers for LLM tasks
- **Retry Policy**: Built-in Celery retry mechanisms

### Environment Variables

Ensure these are set in your environment:

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
OPENAI_API_KEY=your_openai_key
```

## Usage

### Starting the System

1. Start Redis server:
   ```bash
   ./scripts/local/launch_servers.sh
   ```

2. Verify Celery workers are running:
   ```bash
   celery -A task_queue worker -Q llm_queue --loglevel=INFO
   ```

### Testing

Run the test script to verify functionality:

```bash
python test_async_classification.py
```

### Manual Testing

1. Start a new grievance conversation
2. Complete the grievance details form
3. Observe that classification starts asynchronously
4. Continue with the conversation while classification runs
5. Check that results appear when classification completes

## Error Handling

### Fallback Mechanisms

1. **No grievance_id**: Falls back to synchronous processing
2. **Celery unavailable**: Falls back to synchronous processing
3. **Task timeout**: Proceeds without classification
4. **Task failure**: Shows error message and continues

### Monitoring

- Task status is logged to Celery logs
- WebSocket notifications for task progress (if enabled)
- Database storage of task results

## Troubleshooting

### Common Issues

1. **Task not starting**:
   - Check Redis connection
   - Verify Celery workers are running
   - Check task queue configuration

2. **Task stuck in processing**:
   - Check Celery worker logs
   - Verify OpenAI API key and quota
   - Check network connectivity

3. **Results not appearing**:
   - Check task status in Celery
   - Verify slot updates in Rasa
   - Check form validation logic

### Debug Commands

```bash
# Check Celery worker status
celery -A task_queue inspect active

# Check task queue
celery -A task_queue inspect stats

# Monitor task results
celery -A task_queue flower
```

## Performance Considerations

### Optimization

1. **Task timeout**: Set appropriate timeouts for LLM calls
2. **Concurrency**: Adjust worker count based on load
3. **Caching**: Consider caching similar classifications
4. **Queue management**: Monitor queue size and processing times

### Monitoring

- Track task completion times
- Monitor failure rates
- Watch queue lengths
- Monitor Redis memory usage

## Future Enhancements

1. **WebSocket progress updates**: Real-time progress notifications
2. **Task prioritization**: Priority queues for urgent classifications
3. **Result caching**: Cache similar classifications
4. **Batch processing**: Process multiple grievances together
5. **Advanced retry logic**: Custom retry strategies for different failure types 