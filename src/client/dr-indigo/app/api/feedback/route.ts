import { NextRequest, NextResponse } from 'next/server';

const LANGFUSE_HOST = process.env.LANGFUSE_HOST || 'https://langfusedev.nh.novant.net';
const LANGFUSE_PUBLIC_KEY = process.env.LANGFUSE_PUBLIC_KEY;
const LANGFUSE_SECRET_KEY = process.env.LANGFUSE_SECRET_KEY;

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { messageId, rating, message, timestamp } = body;

    console.log('Received feedback:', { messageId, rating, message });

    if (!LANGFUSE_PUBLIC_KEY || !LANGFUSE_SECRET_KEY) {
      console.error('Missing Langfuse credentials');
      return NextResponse.json(
        { error: 'Langfuse credentials not configured' },
        { status: 500 }
      );
    }

    const authString = Buffer.from(`${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY}`).toString('base64');

    // Get the most recent trace from Langfuse
    let traceId = null;
    
    try {
      const tracesResponse = await fetch(
        `${LANGFUSE_HOST}/api/public/traces?page=1&limit=1`,
        {
          headers: {
            'Authorization': `Basic ${authString}`,
          },
        }
      );

      if (tracesResponse.ok) {
        const tracesData = await tracesResponse.json();
        
        if (tracesData.data && Array.isArray(tracesData.data) && tracesData.data.length > 0) {
          traceId = tracesData.data[0].id;
          console.log(`✅ Using most recent trace: ${traceId}`);
        } else {
          console.log('⚠️  No traces found');
        }
      } else {
        console.log('⚠️  Failed to fetch traces:', tracesResponse.status);
      }
    } catch (error) {
      console.log('⚠️  Error fetching traces:', error);
    }

    // Create feedback - always try to link to a trace if available
    let eventData;
    
    if (traceId) {
      // Create a score linked to the most recent trace
      eventData = {
        batch: [
          {
            id: `score-${Date.now()}-${Math.random().toString(36).substring(7)}`,
            type: 'score-create',
            timestamp: timestamp || new Date().toISOString(),
            body: {
              id: `score-${Date.now()}-${Math.random().toString(36).substring(7)}`,
              traceId: traceId,
              name: 'user-feedback',
              value: rating,
              comment: message ? `User rated: "${message.substring(0, 100)}${message.length > 100 ? '...' : ''}"` : undefined,
              dataType: 'NUMERIC',
              metadata: {
                messageId: messageId,
                ratingType: rating > 0 ? 'thumbs-up' : 'thumbs-down',
                fullMessage: message,
              },
            },
          },
        ],
      };
      console.log('✅ Creating score for trace:', traceId);
    } else {
      // Create a standalone event if no trace found
      eventData = {
        batch: [
          {
            id: `event-${Date.now()}-${Math.random().toString(36).substring(7)}`,
            type: 'event-create',
            timestamp: timestamp || new Date().toISOString(),
            body: {
              id: `event-${Date.now()}-${Math.random().toString(36).substring(7)}`,
              name: 'user-feedback',
              metadata: {
                messageId: messageId,
                rating: rating,
                ratingType: rating > 0 ? 'thumbs-up' : 'thumbs-down',
                message: message,
              },
            },
          },
        ],
      };
      console.log('⚠️  Creating standalone event (no traces available)');
    }

    console.log('Sending to Langfuse ingestion API');

    const response = await fetch(`${LANGFUSE_HOST}/api/public/ingestion`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Basic ${authString}`,
      },
      body: JSON.stringify(eventData),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Langfuse API error:', response.status, errorText);
      return NextResponse.json(
        { error: 'Failed to send feedback to Langfuse', details: errorText },
        { status: response.status }
      );
    }

    const result = await response.json();
    console.log('Feedback sent to Langfuse successfully:', result);

    return NextResponse.json({ 
      success: true, 
      result,
      linkedToTrace: !!traceId 
    });
  } catch (error) {
    console.error('Error processing feedback:', error);
    return NextResponse.json(
      { error: 'Internal server error', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
