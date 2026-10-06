FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

# rm -rf dist: fuerza un build limpio en cada arranque (en Windows el bind-mount a
# veces no reescribía el dist y se servía un bundle viejo).
CMD ["sh", "-c", "rm -rf dist && npx vite build && npm run preview"]
