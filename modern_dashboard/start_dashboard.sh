#!/bin/bash

echo "🚀 Starting Lead Recovery Modern Dashboard"
echo "=========================================="

# Check if we're in the right directory
if [ ! -d "frontend" ] || [ ! -d "backend" ]; then
    echo "❌ Error: Please run this script from the modern_dashboard directory"
    exit 1
fi

# Function to cleanup background processes
cleanup() {
    echo "🛑 Shutting down servers..."
    pkill -f "uvicorn"
    pkill -f "next"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

echo "📦 Starting backend server (FastAPI)..."
cd backend
python main.py &
BACKEND_PID=$!
cd ..

echo "⏳ Waiting for backend to start..."
sleep 3

echo "🎨 Starting frontend server (Next.js)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Dashboard is starting up!"
echo "📊 Backend API: http://localhost:8000"
echo "🎨 Frontend UI: http://localhost:3000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "💡 Tips:"
echo "  • The dashboard will open automatically in your browser"
echo "  • Use Ctrl+C to stop both servers"
echo "  • Check the terminal for any error messages"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID 