FROM ubuntu:18.04

LABEL maintainer "Jesse Bowling <jessebowling@gmail.com>"
LABEL name "chn-intel-feeds"
LABEL version "1.8"
LABEL release "1"
LABEL summary "Community Honey Network intel feeds server"
LABEL description "Small App for reading from a CIF instance and generating static feeds consumable via HTTP requests"
LABEL authoritative-source-url "https://github.com/CommunityHoneyNetwork/hpfeeds-logger"
LABEL changelog-url "https://github.com/CommunityHoneyNetwork/hpfeeds-logger/commits/master"

RUN apt-get update \
    && apt-get upgrade -y
RUN apt-get install -y python3 python3-pip runit build-essential python3-dev

ADD . /opt/

RUN pip3 install -r /opt/requirements.txt

RUN mkdir /etc/service/chn-intel-feeds && chmod 0755 /etc/service/chn-intel-feeds
COPY chn-intel-feeds.run /etc/service/chn-intel-feeds/run
RUN chmod 0755 /etc/service/chn-intel-feeds/run

RUN mkdir /etc/service/simple-web-server && chmod 0755 /etc/service/simple-web-server
COPY simple-web-server.run /etc/service/simple-web-server/run
RUN chmod 0755 /etc/service/simple-web-server/run

ENTRYPOINT ["/usr/bin/runsvdir", "-P", "/etc/service"]
