ARG GO_VERSION=1.25.8
ARG PROJECT_NAME

FROM --platform=$BUILDPLATFORM clojure:temurin-21-tools-deps-bookworm AS build
WORKDIR /src
COPY . .
RUN clojure -T:build uberjar

FROM eclipse-temurin:21-jre-noble AS runtime
COPY --from=build /src/target/app.jar /usr/local/app.jar
ENTRYPOINT ["java", "-jar", "/usr/local/app.jar"]
