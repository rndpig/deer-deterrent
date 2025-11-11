FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application files
COPY . .

# Accept build arguments
ARG VITE_API_URL
ARG VITE_DISABLE_AUTH=false

# Set environment variables for Vite build
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_DISABLE_AUTH=$VITE_DISABLE_AUTH

# Expose port
EXPOSE 3000

# Start dev server (for local development)
# For production, you'd use: RUN npm run build && serve dist
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
