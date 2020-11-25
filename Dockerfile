FROM ubuntu:18.04

LABEL maintainer="Team Stingar <team-stingar@duke.edu>"
LABEL name="chn-intel-feeds"
LABEL version="1.9.1"
LABEL release="1"
LABEL summary="Community Honey Network intel feeds server"
LABEL description="Small App for reading from a CIF instance and generating static feeds consumable via HTTP requests"
LABEL authoritative-source-url="https://github.com/CommunityHoneyNetwork/chn-intel-feeds"
LABEL changelog-url="https://github.com/CommunityHoneyNetwork/hpfeeds-logger/commits/master"

ENV DEBIAN_FRONTEND "noninteractive"

# hadolint ignore=DL3008,DL3005
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y python3 python3-pip runit build-essential python3-dev python3-distutils\
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /opt/
# hadolint ignore=DL3013
RUN python3 -m pip install --upgrade pip setuptools wheel \
  && python3 -m pip install -r /opt/requirements.txt

RUN mkdir /etc/service/chn-intel-feeds && chmod 0755 /etc/service/chn-intel-feeds
COPY chn-intel-feeds.run /etc/service/chn-intel-feeds/run
RUN chmod 0755 /etc/service/chn-intel-feeds/run

RUN mkdir /etc/service/simple-web-server && chmod 0755 /etc/service/simple-web-server
COPY simple-web-server.run /etc/service/simple-web-server/run
RUN chmod 0755 /etc/service/simple-web-server/run

RUN mkdir /etc/service/chn-intel-safelist && chmod 0755 /etc/service/chn-intel-safelist
COPY chn-intel-safelist.run /etc/service/chn-intel-safelist/run
RUN chmod 0755 /etc/service/chn-intel-safelist/run

RUN mkdir /etc/service/chn-api-feeds && chmod 0755 /etc/service/chn-api-feeds
COPY chn-api-feeds.run /etc/service/chn-api-feeds/run
RUN chmod 0755 /etc/service/chn-api-feeds/run

ENTRYPOINT ["/usr/bin/runsvdir", "-P", "/etc/service"]
