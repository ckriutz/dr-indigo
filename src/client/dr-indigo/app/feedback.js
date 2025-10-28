/**
 * Handle thumbs up feedback for a message
 * @param {Object} message - The message object from CopilotKit
 */
export async function handleThumbsUp(message) {
  console.log("Thumbs up clicked:", message);
  
  try {
    // Send feedback to Langfuse via backend endpoint
    const response = await fetch('/api/feedback', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messageId: message.id,
        rating: 1, // 1 for thumbs up
        message: message.content,
        timestamp: new Date().toISOString(),
      }),
    });

    if (!response.ok) {
      console.error('Failed to send feedback to Langfuse');
    } else {
      const result = await response.json();
      console.log('Thumbs up feedback sent successfully:', result);
    }
  } catch (error) {
    console.error('Error sending thumbs up feedback:', error);
  }
}

/**
 * Handle thumbs down feedback for a message
 * @param {Object} message - The message object from CopilotKit
 */
export async function handleThumbsDown(message) {
  console.log("Thumbs down clicked:", message);
  
  try {
    // Send feedback to Langfuse via backend endpoint
    const response = await fetch('/api/feedback', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messageId: message.id,
        rating: -1, // -1 for thumbs down
        message: message.content,
        timestamp: new Date().toISOString(),
      }),
    });

    if (!response.ok) {
      console.error('Failed to send feedback to Langfuse');
    } else {
      const result = await response.json();
      console.log('Thumbs down feedback sent successfully:', result);
    }
  } catch (error) {
    console.error('Error sending thumbs down feedback:', error);
  }
}
